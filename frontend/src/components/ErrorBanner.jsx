export default function ErrorBanner({ message, onDismiss }) {
  return (
    <div className="error-banner">
      <span>⚠ ERROR: {message}</span>
      <button className="error-dismiss" onClick={onDismiss}>
        [X] DISMISS
      </button>
    </div>
  )
}
