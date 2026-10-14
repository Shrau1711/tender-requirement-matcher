import { useEffect, useState } from "react";

/** Runs an async loader when its inputs change and reports { data, error, loading }. */
export function useAsync(load, inputs) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  useEffect(() => {
    let current = true;
    setState((s) => ({ ...s, loading: true }));
    load()
      .then((data) => current && setState({ data, error: null, loading: false }))
      .catch((error) => current && setState({ data: null, error: error.message, loading: false }));
    return () => { current = false; };
  }, inputs); // eslint-disable-line react-hooks/exhaustive-deps
  return state;
}
