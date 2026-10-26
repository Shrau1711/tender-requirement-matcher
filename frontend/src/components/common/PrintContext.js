import { createContext, useContext } from "react";

/** True while the whole report is being laid out for printing, so tables show every row instead of one page. */
export const PrintContext = createContext(false);
export const usePrinting = () => useContext(PrintContext);
