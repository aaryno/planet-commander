# Pipeline Stage Metrics — Journey of a Scene

Formal mapping of each pipeline stage to its metrics, Grafana dashboards, and product filter capabilities.
Used by both the PipelineSankey and PipelineGraph visualizations in the Heartbeat page.

**Data source**: `heartbeat-collector.py` queries Prometheus via Grafana Cloud proxy every 30s.
**Collector**: `~/tools/db/heartbeat-collector.py` → `heartbeat_snapshots` table.
**API**: `GET /api/heartbeat/current` → all top-level metrics.
**Detail APIs**: `GET /api/heartbeat/orders-detail`, `GET /api/heartbeat/subs-detail`.

---

## Zone 0: Acquisition (Conserved — scenes/hr)

### Ground Stations → Ingest
| Field | PromQL | Collector Key | Unit |
|-------|--------|---------------|------|
| Ingest rate | `sum(rate(planet_pipeline_jobs_api_objects_jobs_completed{program=~"ps_ingest.*"}[5m]))*3600` | `ingest_per_hour` | scenes/hr |
| SkySat rate | `sum(rate(planet_pipeline_jobs_api_objects_jobs_completed{program=~"skysat_process.*"}[5m]))*3600` | `skysat_rate` | scenes/hr |
| Pelican/Tanager | `sum(rate(planet_pipeline_jobs_api_objects_jobs_completed{program=~"pelican.*\|tanager.*"}[5m]))*3600` | `pelican_tanager_rate` | scenes/hr |

**Grafana**: No dedicated ingest dashboard in D&D. Use Jobs platform dashboards.
**Product filter**: Separate collector keys per constellation. Sankey uses these directly.

### Processing (strip_stats → product_processor)
| Field | PromQL | Collector Key | Unit |
|-------|--------|---------------|------|
| Processing rate | `sum(rate(planet_pipeline_jobs_api_objects_jobs_completed{program=~"product-processor.*\|strip-stats\|cloud-map\|bundle-adjust"}[5m]))*3600` | `processing_per_hour` | ops/hr |
| Anchor ops | `sum(rate(planet_pipeline_jobs_api_objects_jobs_completed{program="ps_all_anchor_operations"}[5m]))*3600` | `anchor_ops_per_hour` | ops/hr |

**Grafana**: Jobs platform dashboards.
**Product filter**: By program name (ps_ingest vs skysat_process vs pelican_collect).

### Rectification
| Field | PromQL | Collector Key | Unit |
|-------|--------|---------------|------|
| Rectify rate | `sum(rate(planet_pipeline_jobs_api_objects_jobs_completed{program=~"rectify.*\|rer.*\|rectification_accuracy"}[5m]))*3600` | `rectify_per_hour` | scenes/hr |

**Note**: Rectification is a processing step, NOT a product. Applies to all constellations.
**Product filter**: By program name (rectify, rectify-ss, rectify-runner-pelican, rectify-runner-tanager).

### Publishing
| Field | PromQL | Collector Key | Unit |
|-------|--------|---------------|------|
| Publish rate | `sum(rate(planet_pipeline_esindexers_index_latency_timing_count[5m]))*3600` | `publish_rate` | scenes/hr |
| Publish latency | `histogram_quantile(0.5, sum(rate(planet_pipeline_esindexers_index_latency_timing_bucket[5m])) by (le))` | `publish_latency_ms` | ms |

**Grafana**: [Production API Stats](https://planet.grafana.net/d/d7818ad1-eea0-40f3-97a2-3267f3f47279)
**Product filter**: None at publish level.

---

## Zone 1: Transformation (Scale Breaks)

### G4 Processing
| Field | PromQL | Grafana Dashboard | Unit |
|-------|--------|-------------------|------|
| Queued tasks | `g4_cluster_current_tasks{status="QUEUED"}` | [G4 Tasks](https://planet.grafana.net/d/aa571e75-43ac-405a-b77e-3333bf3c6e6c) | tasks |
| Task success | `g4_cluster_hourly_tasks{status="SUCCEEDED"}` | [G4 Tasks](https://planet.grafana.net/d/aa571e75-43ac-405a-b77e-3333bf3c6e6c) | tasks/hr |
| Activation time | `g4_data_collect_task_manager_preparation_time_bucket` | [Activation Stats](https://planet.grafana.net/d/deavpes7dshdsb) | seconds |
| Pool size | `g4_pool_pool_running_size` | [G4 Pools](https://planet.grafana.net/d/af61ae59-6a0f-4d16-b0ce-10d41c0ba274) | pods |
| Backlog age | `g4_cluster_namespace_backlog_max_over_time` | [G4 Tasks](https://planet.grafana.net/d/aa571e75-43ac-405a-b77e-3333bf3c6e6c) | seconds |

**Product filter**: `item_type` label on DataCollect metrics (PSScene, SkySatScene, PelicanScene, TanagerScene).
**Cluster → workload mapping**:
- g4c-sub-01/03/04 = Subscriptions
- g4c-live-03, g4c-pioneer-05 = Orders
- g4c-fusion-01/02/03 = Fusion
- g4c-analytics-01 = SIF/Analytics
- g4c-skysat-01 = SkySat ortho

### Fusion (L3H)
| Field | PromQL Source | Collector Key | Unit |
|-------|---------------|---------------|------|
| L3H throughput | Jobs program: `l3h-blending`, `l3h-cestemaoi-*`, etc. | Via `programs` array | tiles/hr |

**Grafana**: G4 Fusion clusters (g4c-fusion-01/02/03) in [G4 Tasks](https://planet.grafana.net/d/aa571e75-43ac-405a-b77e-3333bf3c6e6c)
**Product filter**: Cluster-level only (all fusion is PlanetScope-derived).

### Mosaics
| Field | PromQL Source | Collector Key | Unit |
|-------|---------------|---------------|------|
| Mosaic throughput | Jobs program: `mosaic`, `mosaic_exec`, `mosaic_monitor` | Via `programs` array | tiles/hr |

**Grafana**: Jobs platform dashboards.
**Product filter**: None (mosaics are PlanetScope composites).

---

## Zone 2: Delivery (Expanded — deliveries/hr)

### Orders API (ordersv2)
| Field | PromQL | Collector Key | Unit |
|-------|--------|---------------|------|
| Delivery rate | `sum(rate(ordersv2_updater_publish_to_finish_duration_secs_count[5m]))*3600` | `orders_rate` | orders/hr |
| Products delivered | `sum(rate(ordersv2_worker_order_products_success_count[5m]))*3600` | Detail API | items/hr |
| Products failed | `sum(rate(ordersv2_worker_order_products_failed_count[5m]))*3600` | Detail API | items/hr |
| Queue size | `sum(ordersv2_director_live_view_queued_count)` | `orders_queued` | orders |
| Running | `sum(ordersv2_director_live_view_running_count)` | `orders_running` | orders |
| Success rate | success / (success + failed) * 100 | `orders_success_rate` | % |
| E2E latency P50 | `histogram_quantile(0.5, sum(rate(ordersv2_worker_order_create_to_uow_finish_duration_secs_bucket[5m])) by (le))` | `orders_latency_p50` | seconds |

**Detail API** (`/api/heartbeat/orders-detail`): 4-stage SLI breakdown (request→queue, queue→workflow, create→start, create→finish) at P50/P95.

**Grafana**:
- [Orders API](https://planet.grafana.net/d/Ik8Sztf4k) — operational
- [OrdersV2 SLIs](https://planet.grafana.net/d/iqRkSMa4z) — SLI latencies, `$item_types` dropdown
- [Org-specific Orders](https://planet.grafana.net/d/bdm0iwecyk074e) — per-customer

**Product filter**: `item_types` label (e.g., `[PSScene]`, `[SkySatScene]`, `[PelicanScene]`, `[TanagerScene]`). Available in SLIs dashboard via dropdown.

### Subscriptions (iris + fair-queue)
| Field | PromQL | Collector Key | Unit |
|-------|--------|---------------|------|
| Delivery rate | `sum(rate(iris_prom_event_completed_count{env="live"}[5m]))*3600` | `subs_rate` | items/hr |
| FQ queue depth | `sum(fair_queue_statistics_visible_message_count)` | `subs_queued` | messages |
| FQ oldest msg | `max(fair_queue_statistics_oldest_message_time_ms)/1000` | Detail API | seconds |
| FQ wait P50 | `histogram_quantile(0.5, sum(rate(fair_queue_message_time_in_queue_ms_bucket[5m])) by (le))` | `subs_latency_p50` | ms |
| Success rate | ack / (ack + nack) * 100 | `subs_success_rate` | % |

**Detail API** (`/api/heartbeat/subs-detail`): FQ throughput (pushed/pulled/ack/nack), queue depth, wait percentiles, by-group breakdown.

**Grafana**:
- [Subscriptions API](https://planet.grafana.net/d/YuyRzpBVz) — operational
- [fair-queue](https://planet.grafana.net/d/bdc411a1c33a5767d31d3bcf30d8f81b23900fa4) — queue health
- [Scenes Backends](https://planet.grafana.net/d/8UhVfv-4z) — matcher/indexer
- [PV Backends](https://planet.grafana.net/d/deeqj9shpj8qob) — PV product delivery
- [Org-specific Subs](https://planet.grafana.net/d/cfa92f64-8e60-438e-bd58-1e4615f5b985) — per-customer

**Product filter**: `source_type` / `source_name` (scenes, fusion_ps, analysis_ready_ps, basemaps, soil_water_content, etc.) — but NOT per-constellation within "scenes".

### File Transfer (FTL)
| Field | PromQL | Grafana | Unit |
|-------|--------|---------|------|
| Transfer rate | `sum(rate(ftl_prom_worker_transfer_success_count[5m]))*3600` | [FTL](https://planet.grafana.net/d/ae5935m7ty9z4b) | transfers/hr |
| Transfer failures | `sum(rate(ftl_prom_worker_transfer_failure_count[5m]))*3600` | [FTL](https://planet.grafana.net/d/ae5935m7ty9z4b) | failures/hr |
| Bytes transferred | `sum(rate(ftl_prom_worker_transfer_byte_count[5m]))*3600` | [FTL](https://planet.grafana.net/d/ae5935m7ty9z4b) | bytes/hr |
| E2E latency | `ftl_prom_worker_submitted_at_to_finished_at_duration_bucket` | [FTL](https://planet.grafana.net/d/ae5935m7ty9z4b) | seconds |

**Product filter**: None (product-agnostic delivery infrastructure).

---

## Sankey Scale Conversions

The Sankey uses diamond nodes to mark where unit scales change:

| Conversion | Direction | Ratio | Notes |
|-----------|-----------|-------|-------|
| Published scenes → Orders deliveries | 1:N | `orders_rate / publish_rate` | 1 scene → multiple order items (bundles) |
| Published scenes → Subscription deliveries | 1:N | `subs_rate / publish_rate` | 1 scene → many subscription matches |
| Published scenes → Fusion products | N:1 | `fusion_rate / publish_rate` | Many scenes → 1 fusion tile |
| Published scenes → Mosaics | N:1 | `mosaic_rate / publish_rate` | Many scenes → 1 mosaic tile |

---

## Grafana Deep-Link Map (for node click → Grafana)

| Node ID | Grafana Dashboard | UID | Notes |
|---------|------------------|-----|-------|
| `gs` | — | — | No dashboard (static node) |
| `ps_ingest` | Jobs Platform | — | Jobs program dashboard |
| `processing` | Jobs Platform | — | Jobs program dashboard |
| `rectify` | Jobs Platform | — | Jobs program dashboard |
| `publish` | [Prod API Stats](https://planet.grafana.net/d/d7818ad1-eea0-40f3-97a2-3267f3f47279) | `d7818ad1...` | Publish latency |
| `g4_ord` | [G4 Tasks](https://planet.grafana.net/d/aa571e75-43ac-405a-b77e-3333bf3c6e6c) | `aa571e75...` | Filter: g4c-live-03,pioneer-05 |
| `g4_sub` | [G4 Tasks](https://planet.grafana.net/d/aa571e75-43ac-405a-b77e-3333bf3c6e6c) | `aa571e75...` | Filter: g4c-sub-01,03,04 |
| `g4_fus` | [G4 Tasks](https://planet.grafana.net/d/aa571e75-43ac-405a-b77e-3333bf3c6e6c) | `aa571e75...` | Filter: g4c-fusion-01,02,03 |
| `g4_ss` | [G4 Tasks](https://planet.grafana.net/d/aa571e75-43ac-405a-b77e-3333bf3c6e6c) | `aa571e75...` | Filter: g4c-skysat-01 |
| `orders` | [OrdersV2 SLIs](https://planet.grafana.net/d/iqRkSMa4z) | `iqRkSMa4z` | `$item_types` for product filter |
| `subs` | [Subscriptions API](https://planet.grafana.net/d/YuyRzpBVz) | `YuyRzpBVz` | `source_name` for derived products |
| `fusion` | [G4 Tasks](https://planet.grafana.net/d/aa571e75-43ac-405a-b77e-3333bf3c6e6c) (fusion clusters) | `aa571e75...` | Fusion Dev team |
| `mosaics` | Jobs Platform | — | Mosaic Supervisor |
| `ftl` | [FTL](https://planet.grafana.net/d/ae5935m7ty9z4b) | `ae5935m7ty9z4b` | File transfer |
| `activation` | [Activation Stats](https://planet.grafana.net/d/deavpes7dshdsb) | `deavpes7dshdsb` | Per-constellation panels |
| `pv` | [PV Backends](https://planet.grafana.net/d/deeqj9shpj8qob) | `deeqj9shpj8qob` | PV delivery |
| `sif` | [Analytics API (SIF)](https://planet.grafana.net/d/aeer7ha7pemtca) | `aeer7ha7pemtca` | Delta team |

---

## Per-Product Filtering Capabilities

| Sankey Node | Can Filter By Constellation | Can Filter By Derived Product | How |
|-------------|---------------------------|------------------------------|-----|
| Ingest | ✅ Separate collector keys | N/A | `ingest_per_hour`, `skysat_rate`, `pelican_tanager_rate` |
| Processing | ✅ By program name | N/A | Program contains constellation name |
| Rectification | ✅ By program name | N/A | rectify vs rectify-ss vs rectify-pelican |
| Publishing | ❌ | ❌ | Aggregate only |
| G4 Processing | ✅ `item_type` label | ❌ | PromQL: `{item_type="PelicanScene"}` |
| Orders | ✅ `item_types` label | ✅ `source_type` | OrdersV2 SLIs dropdown |
| Subscriptions | ❌ (lumped in "scenes") | ✅ `source_name` | FQ routing_key encodes source_type |
| FTL | ❌ | ❌ | Product-agnostic |
| Fusion | N/A (PlanetScope only) | N/A | Cluster-level filter |
| Mosaics | N/A (PlanetScope only) | N/A | — |
| PV Products | N/A | ✅ Per-product source_type | Individual PV dashboards |
| SIF/Analytics | N/A | ✅ Feed ID | Delta team dashboard |
