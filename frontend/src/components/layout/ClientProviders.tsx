"use client";

import { useEffect, type ReactNode } from "react";
import { CartProvider } from "@/lib/cart";
import { CartDrawer } from "@/components/cart/CartDrawer";
import { loadUrls } from "@/lib/urls";

export function ClientProviders({ children }: { children: ReactNode }) {
  useEffect(() => {
    loadUrls();
  }, []);

  return (
    <CartProvider>
      {children}
      <CartDrawer />
    </CartProvider>
  );
}
