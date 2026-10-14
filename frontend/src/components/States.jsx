export function EmptyState({ title, children, action }) {
  return (
    <div className="empty">
      <h2>{title}</h2>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ title = "Something went wrong", children }) {
  return (
    <div className="problem" role="alert">
      <h2>{title}</h2>
      <p>{children}</p>
    </div>
  );
}
