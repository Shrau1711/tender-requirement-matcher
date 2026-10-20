import { useEffect, useState } from "react";
import { api } from "../api";
import { ErrorState } from "../components/States";

const seconds = (since) => Math.max(0, Math.round((Date.now() - new Date(since).getTime()) / 1000));
const clock = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

function Estimate({ run }) {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState(null);
  const { estimate } = run;
  async function answer(call) {
    setBusy(true); setProblem(null);
    try { await call(run.id); } catch (e) { setProblem(e.message); setBusy(false); }
  }
  return (
    <div className="card stack">
      <h1 id="run-title" tabIndex={-1}>Ready to match</h1>
      <p className="muted">{run.tender}</p>
      {estimate.questions > 0 ? (
        <ul>
          <li><strong>{estimate.questions}</strong> new questions for the language model, covering {estimate.requirements} requirements. Answers it already has cost nothing.</li>
          <li>About <strong>₹{estimate.rupees}</strong> of model credit.</li>
          <li>Roughly <strong>{estimate.minutes_low}–{estimate.minutes_high} minutes</strong>. This is a guess: the model's speed varies.</li>
        </ul>
      ) : (
        <p>Everything this needs is already saved, so it costs nothing. Reading the manufacturers' documents still takes a minute or two, longer for a big pump tender.</p>
      )}
      {estimate.notes.map((note) => <p key={note} className="notice">{note}</p>)}
      {problem && <div className="problem" role="alert">{problem}</div>}
      <div className="actions">
        <button className="button" disabled={busy} onClick={() => answer(api.proceed)}>{busy ? "Starting…" : "Proceed"}</button>
        <button className="button secondary" disabled={busy} onClick={() => answer(api.cancel)}>Cancel</button>
      </div>
    </div>
  );
}

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
  if (run.status === "cancelled") {
    return (
      <div className="stack">
        <h1 id="run-title" tabIndex={-1}>Cancelled</h1>
        <p className="notice">{run.tender} was not matched. Nothing was spent on the manufacturers' documents, and the answers already saved are kept, so uploading it again picks up from there.</p>
      </div>
    );
  }
  if (run.status === "awaiting" && run.estimate) return <Estimate run={run} />;
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
