export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <p className="status-message status-message--loading" role="status">
      {label}
    </p>
  );
}

export function ErrorMessage({ message }: { message: string }) {
  return (
    <p className="status-message status-message--error" role="alert">
      {message}
    </p>
  );
}

export function EmptyState({ message }: { message: string }) {
  return <p className="status-message status-message--empty">{message}</p>;
}
