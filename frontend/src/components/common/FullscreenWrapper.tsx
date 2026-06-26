import { useState, useEffect, useCallback } from "react";
import { Button } from "antd";
import { FullscreenOutlined, FullscreenExitOutlined } from "@ant-design/icons";

type RenderFn = (isFullscreen: boolean) => React.ReactNode;

interface Props {
  /** Children or render function: render(isFullscreen) => node */
  children: React.ReactNode | RenderFn;
  /** Optional toolbar rendered alongside the fullscreen button */
  toolbar?: React.ReactNode;
}

export default function FullscreenWrapper({ children, toolbar }: Props) {
  const [fs, setFs] = useState(false);

  const exit = useCallback(() => setFs(false), []);

  useEffect(() => {
    if (!fs) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") exit();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fs, exit]);

  const render = typeof children === "function" ? (children as RenderFn) : undefined;

  return (
    <>
      {/* Inline toolbar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 8,
        }}
      >
        <div style={{ flex: 1 }}>{toolbar}</div>
        <Button
          type="text"
          size="small"
          icon={fs ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
          onClick={() => setFs(!fs)}
        />
      </div>

      {/* Inline editor */}
      <div
        style={{
          border: "1px solid #d9d9d9",
          borderRadius: 6,
          overflow: "hidden",
          display: fs ? "none" : undefined,
        }}
      >
        {render ? render(false) : (children as React.ReactNode)}
      </div>

      {/* Fullscreen overlay */}
      {fs && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 1000,
            background: "#1e1e1e",
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              padding: "8px 16px",
              borderBottom: "1px solid rgba(255,255,255,0.1)",
            }}
          >
            <Button
              type="text"
              icon={<FullscreenExitOutlined style={{ color: "#fff" }} />}
              onClick={exit}
            >
              <span style={{ color: "#fff" }}>退出全屏 (Esc)</span>
            </Button>
          </div>
          <div style={{ flex: 1, overflow: "hidden" }}>
            {render ? render(true) : (children as React.ReactNode)}
          </div>
        </div>
      )}
    </>
  );
}
