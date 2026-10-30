export function LoadingState({ label = "Loading data…" }: { label?: string }) {
  return (
    <div className="state-block" role="status">
      <div className="spinner" aria-hidden="true" />
      <p>{label}</p>
    </div>
  );
}

export function EmptyState({
  title,
  hint,
}: {
  title: string;
  hint?: string;
}) {
  return (
    <div className="state-block empty">
      <p className="state-title">{title}</p>
      {hint ? <p className="state-hint">{hint}</p> : null}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="state-block error" role="alert">
      <p className="state-title">Something went wrong</p>
      <p className="state-hint">{message}</p>
      <button className="btn" onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}
