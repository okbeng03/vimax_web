import { useEffect, useRef } from "react";

interface Props {
  outputLines: string[];
}

export default function TerminalView({ outputLines }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [outputLines.length]);

  return (
    <div
      ref={containerRef}
      style={{
        height: 400,
        backgroundColor: "#1e1e1e",
        color: "#d4d4d4",
        fontFamily: "'Menlo', 'Monaco', 'Courier New', monospace",
        fontSize: 13,
        padding: 12,
        borderRadius: 6,
        overflowY: "auto",
        whiteSpace: "pre-wrap",
        wordBreak: "break-all",
      }}
    >
      {outputLines.length === 0 ? (
        <span style={{ color: "#808080" }}>等待输出...</span>
      ) : (
        outputLines.map((line, i) => (
          <div key={i}>{line}</div>
        ))
      )}
    </div>
  );
}
