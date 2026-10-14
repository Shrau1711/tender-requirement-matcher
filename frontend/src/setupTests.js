import "@testing-library/jest-dom/vitest";

window.scrollTo = () => {};  // jsdom does not implement it
HTMLCanvasElement.prototype.getContext = () => null;  // axe probes the canvas; jsdom has none
