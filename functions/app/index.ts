// Qoder Sites Edge Function entry point.
// Secrets: HARNESS_BACKEND_URL and HARNESS_SHARED_TOKEN.
import { handleRequest } from "./proxy.ts";

Deno.serve((request: Request) =>
  handleRequest(
    request,
    Deno.env.get("HARNESS_BACKEND_URL") ?? "",
    Deno.env.get("HARNESS_SHARED_TOKEN") ?? "",
  )
);
