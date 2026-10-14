import { useEffect, useState } from "react";
import { ErrorState } from "../components/States";

const seconds = (since) => Math.max(0, Math.round((Date.now() - new Date(since).getTime()) / 1000));
const clock = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export default function RunStatus({ run, error }) {
  const [, setTick] = useState(0);  // a new second: show the new elapsed time
  useEffect(() => {
    const timer = setInterval(() => setTick((n) => n + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  if (error) return <ErrorState title="Could not load this run">{error}</ErrorState>;
  if (!run) return <p className="muted" role="status">Loading the run…</p>;
  if (run.status === "failed") {
    return (
      <div className="stack">
        <ErrorState title="This run failed">{run.error}</ErrorState>
        <p className="notice">Anything the model had already answered is saved, so uploading the tender again picks up where it stopped.</p>
      </div>
    );
  }
  return (
    <div className="card progress-card">
      <h1 id="run-title" tabIndex={-1}>{run.status === "queued" ? "Waiting for its turn" : "Matching in progress"}</h1>
      <p className="muted">{run.tender}</p>
      <div className="bar" aria-hidden="true"><span /></div>
      <p role="status"><strong>{run.progress ?? "Starting"}</strong></p>
      <p className="hint">Running for {clock(seconds(run.created_at))}. This takes a few minutes; you can leave this page and come back from Runs.</p>
    </div>
  );
}
