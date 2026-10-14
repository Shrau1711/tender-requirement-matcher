import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

const NotifyContext = createContext(() => {});
const SHOW_MS = 5000;
const SHOW_WITH_ACTION_MS = 12000;  // long enough to notice a mistake and press Undo

/** Short messages ("Saved", "Could not save"). A message can carry one action, such as Undo. Announced to screen readers. */
export function NotifyProvider({ children }) {
  const [message, setMessage] = useState(null);
  const timer = useRef();
  const notify = useCallback((text, action = null) => {
    setMessage({ text, action });
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setMessage(null), action ? SHOW_WITH_ACTION_MS : SHOW_MS);
  }, []);
  useEffect(() => () => clearTimeout(timer.current), []);
  return (
    <NotifyContext.Provider value={notify}>
      {children}
      <div role="status" aria-live="polite" className={message ? "toast" : "visually-hidden"}>
        {message?.text}
        {message?.action && (
          <button className="toast-action" onClick={() => { message.action.run(); setMessage(null); }}>{message.action.label}</button>
        )}
      </div>
    </NotifyContext.Provider>
  );
}

export const useNotify = () => useContext(NotifyContext);
