import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useNotify } from "../components/shell/Notifier";

/** The decisions people have recorded for one run, and a way to record more. They never change the computed score. */
export function useReviews(runId) {
  const notify = useNotify();
  const [decisions, setDecisions] = useState(() => new Map());

  useEffect(() => {
    let current = true;
    api.reviews(runId)
      .then((list) => current && setDecisions(new Map(list.map((r) => [r.key, r]))))
      .catch((e) => notify(`Could not load saved decisions: ${e.message}`));
    return () => { current = false; };
  }, [runId, notify]);

  const save = useCallback(async (items, message, action = null) => {
    try {
      const list = await api.saveReviews(runId, items);
      setDecisions(new Map(list.map((r) => [r.key, r])));
      if (message) notify(message, action);
      return true;
    } catch (e) {
      notify(`Could not save: ${e.message}`);
      return false;
    }
  }, [runId, notify]);

  return { decisions, save };
}
