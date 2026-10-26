import { useRef } from "react";

/** Tabs that work with the arrow keys, Home and End. The panels are rendered by the caller with TabPanel. */
export function Tabs({ tabs, selected, onSelect, name }) {
  const refs = useRef({});
  function onKeyDown(event) {
    const at = tabs.findIndex((t) => t.id === selected);
    const to = { ArrowRight: (at + 1) % tabs.length, ArrowLeft: (at - 1 + tabs.length) % tabs.length, Home: 0, End: tabs.length - 1 }[event.key];
    if (to === undefined) return;
    event.preventDefault();
    onSelect(tabs[to].id);
    refs.current[tabs[to].id]?.focus();
  }
  return (
    <div role="tablist" aria-label={name} className="tabs" onKeyDown={onKeyDown}>
      {tabs.map((t) => (
        <button
          key={t.id} ref={(el) => { refs.current[t.id] = el; }} role="tab" id={`tab-${t.id}`} className="tab"
          aria-selected={t.id === selected} aria-controls={`panel-${t.id}`} tabIndex={t.id === selected ? 0 : -1} onClick={() => onSelect(t.id)}
        >
          {t.label}{t.count != null && <span className="count">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function TabPanel({ id, label, selected, printing, children }) {
  return (
    <div role="tabpanel" id={`panel-${id}`} aria-labelledby={`tab-${id}`} aria-label={label} tabIndex={0} hidden={!printing && selected !== id}>
      {(printing || selected === id) && children}
    </div>
  );
}
