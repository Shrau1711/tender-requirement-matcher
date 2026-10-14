import { useMemo } from "react";
import { countsOf, percent } from "../lib/format";
import { rowsOf } from "../lib/review";
import DataTable from "./DataTable";
import StatusStrip from "./StatusStrip";

/** Manufacturers ranked by compatibility. Choosing one opens its requirements. */
export default function Ranking({ makers, onOpen }) {
  const columns = useMemo(() => [
    { key: "rank", label: "Rank", render: (m) => <span className="rank-cell">{m.rank ?? "–"}</span>, sortValue: (m) => m.rank ?? 99 },
    { key: "manufacturer", label: "Manufacturer", render: (m) => <button className="link-button" onClick={() => onOpen(m.manufacturer)}>{m.manufacturer}</button> },
    { key: "compatibility", label: "Compatibility", numeric: true, render: (m) => <span className="score-cell">{percent(m.compatibility)}</span>, sortValue: (m) => m.compatibility ?? -1 },
    { key: "mix", label: "What the score is made of", sortable: false, render: (m) => <StatusStrip counts={countsOf(rowsOf(m))} /> },
    { key: "unsupported", label: "Not scored", numeric: true, sortValue: (m) => countsOf(rowsOf(m))["unsupported requirement"], render: (m) => countsOf(rowsOf(m))["unsupported requirement"] },
    { key: "review_needed", label: "To check", numeric: true },
  ], [onOpen]);
  return <DataTable caption="Manufacturers ranked by compatibility with the tender" columns={columns} rows={makers} rowKey={(m) => m.manufacturer} defaultSort={{ key: "rank", direction: "ascending" }} pageSize={50} />;
}
