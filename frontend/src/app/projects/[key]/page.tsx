"use client";

import { use } from "react";
import { ProjectDashboard } from "@/components/projects/ProjectDashboard";

export default function ProjectPage({
  params,
}: {
  params: Promise<{ key: string }>;
}) {
  const { key } = use(params);
  return <ProjectDashboard projectKey={key} />;
}
