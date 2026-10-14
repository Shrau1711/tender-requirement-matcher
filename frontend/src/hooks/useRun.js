import { useEffect, useState } from "react";
import { api } from "../api";

const POLL_MS = 3000;

/** Follows one run until it has finished, and loads its report when it is done. */
export function useRun(id, onChange) {
  const [run, setRun] = useState(null);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let current = true;
    let timer;
    setRun(null); setReport(null); setError(null);
    const look = async () => {
      try {
        const info = await api.run(id);
        if (!current) return;
        setRun(info);
        if (info.status === "done") {
          setReport(await api.report(id));
          onChange?.();
        } else if (info.status === "failed") {
          onChange?.();
        } else {
          timer = setTimeout(look, POLL_MS);
        }
      } catch (e) {
        if (current) setError(e.message);
      }
    };
    look();
    return () => { current = false; clearTimeout(timer); };
  }, [id]); // eslint-disable-line react-hooks/exhaustive-deps

  return { run, report, error };
}
