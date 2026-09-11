import type { DocumentStatus } from "../api/types";

const LABELS: Record<DocumentStatus, string> = {
  pending: "Pending",
  processing: "Processing",
  done: "Done",
  failed: "Failed",
};

export function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  return <span className={`doc-status doc-status--${status}`}>{LABELS[status] ?? status}</span>;
}
