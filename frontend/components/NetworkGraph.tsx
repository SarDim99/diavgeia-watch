"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { formatCurrency } from "@/lib/api";
import { Network, ZoomIn, ZoomOut, Maximize2 } from "lucide-react";

interface Node {
  id: string;
  type: "org" | "contractor";
  total: number;
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
}

interface Edge {
  source: string | Node;
  target: string | Node;
  amount: number;
  contracts: number;
}

interface NetworkData {
  nodes: Node[];
  edges: Edge[];
  stats: { org_count: number; contractor_count: number; edge_count: number };
}

export default function NetworkGraph() {
  const [data, setData] = useState<NetworkData | null>(null);
  const [loading, setLoading] = useState(true);
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    content: string;
  } | null>(null);
  const [minAmount, setMinAmount] = useState(30000);
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const simulationRef = useRef<any>(null);
  const transformRef = useRef({ x: 0, y: 0, k: 1 });

  const fetchNetwork = useCallback(async (min: number) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/network?min_amount=${min}&max_edges=80`);
      if (!res.ok) throw new Error("Failed");
      const json = await res.json();
      setData(json);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchNetwork(minAmount);
  }, [minAmount, fetchNetwork]);

  useEffect(() => {
    if (!data || !svgRef.current || !containerRef.current) return;

    const svg = svgRef.current;
    const container = containerRef.current;
    const width = container.clientWidth;
    const height = container.clientHeight;

    // Clear previous
    while (svg.firstChild) svg.removeChild(svg.firstChild);

    // Create defs for arrow markers
    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    const marker = document.createElementNS("http://www.w3.org/2000/svg", "marker");
    marker.setAttribute("id", "arrowhead");
    marker.setAttribute("viewBox", "0 0 10 6");
    marker.setAttribute("refX", "10");
    marker.setAttribute("refY", "3");
    marker.setAttribute("markerWidth", "8");
    marker.setAttribute("markerHeight", "5");
    marker.setAttribute("orient", "auto");
    const arrowPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
    arrowPath.setAttribute("d", "M 0 0 L 10 3 L 0 6 z");
    arrowPath.setAttribute("fill", "#334155");
    marker.appendChild(arrowPath);
    defs.appendChild(marker);
    svg.appendChild(defs);

    // Main group for zoom/pan
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    svg.appendChild(g);

    // Prepare simulation data (deep copy)
    const nodes: Node[] = data.nodes.map((n) => ({ ...n }));
    const nodeMap = new Map(nodes.map((n) => [n.id, n]));

    const edges: Edge[] = data.edges
      .filter((e) => nodeMap.has(e.source as string) && nodeMap.has(e.target as string))
      .map((e) => ({
        ...e,
        source: nodeMap.get(e.source as string)!,
        target: nodeMap.get(e.target as string)!,
      }));

    // Amount scale for edge widths
    const maxAmount = Math.max(...edges.map((e) => e.amount), 1);
    const edgeWidth = (amount: number) =>
      Math.max(1, Math.min(6, (amount / maxAmount) * 6));

    // Node radius scale
    const maxTotal = Math.max(...nodes.map((n) => n.total), 1);
    const nodeRadius = (node: Node) => {
      const base = node.type === "org" ? 12 : 6;
      const scale = Math.sqrt(node.total / maxTotal);
      return base + scale * (node.type === "org" ? 16 : 10);
    };

    // Draw edges
    const edgeElements: SVGLineElement[] = [];
    for (const edge of edges) {
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("stroke", "#1e293b");
      line.setAttribute("stroke-width", String(edgeWidth(edge.amount)));
      line.setAttribute("stroke-opacity", "0.6");
      line.setAttribute("marker-end", "url(#arrowhead)");
      g.appendChild(line);
      edgeElements.push(line);
    }

    // Draw nodes
    const nodeGroups: SVGGElement[] = [];
    for (const node of nodes) {
      const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
      group.style.cursor = "grab";

      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      const r = nodeRadius(node);
      circle.setAttribute("r", String(r));

      if (node.type === "org") {
        circle.setAttribute("fill", "#4f8ff7");
        circle.setAttribute("stroke", "#2563eb");
        circle.setAttribute("stroke-width", "2");
      } else {
        circle.setAttribute("fill", "#f59e0b");
        circle.setAttribute("stroke", "#d97706");
        circle.setAttribute("stroke-width", "1.5");
      }

      // Label
      const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
      const label =
        node.id.length > 20 ? node.id.slice(0, 20) + "…" : node.id;
      text.textContent = label;
      text.setAttribute("text-anchor", "middle");
      text.setAttribute("dy", String(r + 14));
      text.setAttribute("fill", node.type === "org" ? "#94a3b8" : "#64748b");
      text.setAttribute("font-size", node.type === "org" ? "11" : "9");
      text.setAttribute("font-family", "DM Sans, system-ui, sans-serif");
      text.setAttribute("pointer-events", "none");

      group.appendChild(circle);
      group.appendChild(text);
      g.appendChild(group);
      nodeGroups.push(group);

      // Hover
      group.addEventListener("mouseenter", (ev) => {
        circle.setAttribute("stroke-width", "3");
        circle.setAttribute("filter", "brightness(1.2)");
        const rect = svg.getBoundingClientRect();
        setTooltip({
          x: ev.clientX - rect.left,
          y: ev.clientY - rect.top - 12,
          content: `${node.id}\n${node.type === "org" ? "Organization" : "Contractor"}\nTotal: ${formatCurrency(node.total)}`,
        });
      });
      group.addEventListener("mouseleave", () => {
        circle.setAttribute(
          "stroke-width",
          node.type === "org" ? "2" : "1.5"
        );
        circle.removeAttribute("filter");
        setTooltip(null);
      });

      // Drag
      let dragging = false;
      group.addEventListener("mousedown", (ev) => {
        ev.stopPropagation();
        dragging = true;
        group.style.cursor = "grabbing";
        node.fx = node.x;
        node.fy = node.y;

        const onMove = (e: MouseEvent) => {
          if (!dragging) return;
          const t = transformRef.current;
          node.fx = (e.clientX - svg.getBoundingClientRect().left - t.x) / t.k;
          node.fy = (e.clientY - svg.getBoundingClientRect().top - t.y) / t.k;
          sim.alpha(0.3).restart();
        };
        const onUp = () => {
          dragging = false;
          group.style.cursor = "grab";
          node.fx = null;
          node.fy = null;
          sim.alpha(0.1).restart();
          document.removeEventListener("mousemove", onMove);
          document.removeEventListener("mouseup", onUp);
        };
        document.addEventListener("mousemove", onMove);
        document.addEventListener("mouseup", onUp);
      });
    }

    // Simple force simulation (no D3 dependency)
    const sim = {
      alpha: 1,
      alphaTarget: 0,
      alphaDecay: 0.02,
      running: true,
      restart() {
        this.running = true;
        return this;
      },
    } as any;

    // Initialize positions
    for (const node of nodes) {
      node.x = width / 2 + (Math.random() - 0.5) * width * 0.6;
      node.y = height / 2 + (Math.random() - 0.5) * height * 0.6;
      node.vx = 0;
      node.vy = 0;
    }

    // Simulation tick
    function tick() {
      if (!sim.running) return;

      sim.alpha += (sim.alphaTarget - sim.alpha) * sim.alphaDecay;
      if (sim.alpha < 0.001) {
        sim.running = false;
        return;
      }

      // Center gravity
      for (const node of nodes) {
        node.vx! += (width / 2 - node.x!) * 0.001 * sim.alpha;
        node.vy! += (height / 2 - node.y!) * 0.001 * sim.alpha;
      }

      // Link force
      for (let i = 0; i < edges.length; i++) {
        const e = edges[i];
        const s = e.source as Node;
        const t = e.target as Node;
        const dx = t.x! - s.x!;
        const dy = t.y! - s.y!;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const targetDist = 120 + (1 - e.amount / maxAmount) * 80;
        const force = ((dist - targetDist) / dist) * 0.05 * sim.alpha;

        s.vx! += dx * force;
        s.vy! += dy * force;
        t.vx! -= dx * force;
        t.vy! -= dy * force;
      }

      // Repulsion (charge)
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i];
          const b = nodes[j];
          const dx = b.x! - a.x!;
          const dy = b.y! - a.y!;
          const distSq = dx * dx + dy * dy || 1;
          const dist = Math.sqrt(distSq);
          const strength = -300 * sim.alpha;
          const force = strength / distSq;

          a.vx! -= (dx / dist) * force;
          a.vy! -= (dy / dist) * force;
          b.vx! += (dx / dist) * force;
          b.vy! += (dy / dist) * force;
        }
      }

      // Velocity decay and position update
      for (const node of nodes) {
        if (node.fx != null) {
          node.x = node.fx;
          node.y = node.fy!;
          node.vx = 0;
          node.vy = 0;
        } else {
          node.vx! *= 0.6;
          node.vy! *= 0.6;
          node.x! += node.vx!;
          node.y! += node.vy!;
        }
      }

      // Update SVG
      for (let i = 0; i < edges.length; i++) {
        const s = edges[i].source as Node;
        const t = edges[i].target as Node;
        edgeElements[i].setAttribute("x1", String(s.x));
        edgeElements[i].setAttribute("y1", String(s.y));
        edgeElements[i].setAttribute("x2", String(t.x));
        edgeElements[i].setAttribute("y2", String(t.y));
      }

      for (let i = 0; i < nodes.length; i++) {
        nodeGroups[i].setAttribute(
          "transform",
          `translate(${nodes[i].x},${nodes[i].y})`
        );
      }

      requestAnimationFrame(tick);
    }

    sim.alpha = 1;
    sim.running = true;
    requestAnimationFrame(tick);
    simulationRef.current = sim;

    // Zoom/Pan
    let isPanning = false;
    let panStart = { x: 0, y: 0 };

    svg.addEventListener("mousedown", (ev) => {
      isPanning = true;
      panStart = { x: ev.clientX, y: ev.clientY };
      svg.style.cursor = "move";
    });

    svg.addEventListener("mousemove", (ev) => {
      if (!isPanning) return;
      const t = transformRef.current;
      t.x += ev.clientX - panStart.x;
      t.y += ev.clientY - panStart.y;
      panStart = { x: ev.clientX, y: ev.clientY };
      g.setAttribute("transform", `translate(${t.x},${t.y}) scale(${t.k})`);
    });

    svg.addEventListener("mouseup", () => {
      isPanning = false;
      svg.style.cursor = "default";
    });

    svg.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      const t = transformRef.current;
      const scaleFactor = ev.deltaY < 0 ? 1.1 : 0.9;
      const newK = Math.min(3, Math.max(0.2, t.k * scaleFactor));

      // Zoom toward cursor
      const rect = svg.getBoundingClientRect();
      const mx = ev.clientX - rect.left;
      const my = ev.clientY - rect.top;
      t.x = mx - ((mx - t.x) / t.k) * newK;
      t.y = my - ((my - t.y) / t.k) * newK;
      t.k = newK;

      g.setAttribute("transform", `translate(${t.x},${t.y}) scale(${t.k})`);
    });

    return () => {
      sim.running = false;
    };
  }, [data]);

  const zoom = (factor: number) => {
    const svg = svgRef.current;
    if (!svg) return;
    const g = svg.querySelector("g");
    if (!g) return;
    const t = transformRef.current;
    t.k = Math.min(3, Math.max(0.2, t.k * factor));
    g.setAttribute("transform", `translate(${t.x},${t.y}) scale(${t.k})`);
  };

  const resetView = () => {
    const svg = svgRef.current;
    if (!svg) return;
    const g = svg.querySelector("g");
    if (!g) return;
    transformRef.current = { x: 0, y: 0, k: 1 };
    g.setAttribute("transform", "translate(0,0) scale(1)");
  };

  return (
    <div className="rounded-xl border border-navy-600 bg-navy-800 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-navy-600">
        <div className="flex items-center gap-2">
          <Network className="w-4 h-4 text-accent-cyan" />
          <h3 className="font-semibold text-sm">Spending Network</h3>
          {data && (
            <span className="text-xs text-slate-500 font-mono ml-2">
              {data.stats.org_count} orgs · {data.stats.contractor_count}{" "}
              contractors · {data.stats.edge_count} links
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {/* Threshold slider */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">Min amount:</span>
            <select
              value={minAmount}
              onChange={(e) => setMinAmount(Number(e.target.value))}
              className="text-xs bg-navy-700 border border-navy-600 rounded px-2 py-1 text-slate-300"
            >
              <option value={5000}>€5k</option>
              <option value={10000}>€10k</option>
              <option value={30000}>€30k</option>
              <option value={50000}>€50k</option>
              <option value={100000}>€100k</option>
            </select>
          </div>

          {/* Zoom controls */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => zoom(1.3)}
              className="p-1.5 rounded hover:bg-navy-600 text-slate-400 hover:text-white transition-colors"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => zoom(0.7)}
              className="p-1.5 rounded hover:bg-navy-600 text-slate-400 hover:text-white transition-colors"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={resetView}
              className="p-1.5 rounded hover:bg-navy-600 text-slate-400 hover:text-white transition-colors"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Graph */}
      <div
        ref={containerRef}
        className="relative"
        style={{ height: "500px" }}
      >
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-navy-800/80 z-10">
            <div className="flex items-center gap-2 text-slate-400 text-sm">
              <div className="w-4 h-4 border-2 border-accent-blue border-t-transparent rounded-full animate-spin" />
              Loading network...
            </div>
          </div>
        )}

        <svg
          ref={svgRef}
          width="100%"
          height="100%"
          className="bg-navy-900/50"
        />

        {/* Tooltip */}
        {tooltip && (
          <div
            className="absolute pointer-events-none z-20 bg-navy-900 border border-navy-600 rounded-lg px-3 py-2 shadow-xl"
            style={{
              left: tooltip.x + 10,
              top: tooltip.y - 50,
              transform: "translateX(-50%)",
            }}
          >
            {tooltip.content.split("\n").map((line, i) => (
              <p
                key={i}
                className={
                  i === 0
                    ? "text-xs font-medium text-white max-w-[200px] truncate"
                    : "text-[10px] text-slate-400"
                }
              >
                {line}
              </p>
            ))}
          </div>
        )}

        {/* Legend */}
        <div className="absolute bottom-3 left-3 flex items-center gap-4 bg-navy-900/80 rounded-lg px-3 py-2 backdrop-blur-sm border border-navy-600">
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full bg-accent-blue" />
            <span className="text-[10px] text-slate-400">Organization</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full bg-accent-amber" />
            <span className="text-[10px] text-slate-400">Contractor</span>
          </div>
          <span className="text-[10px] text-slate-500">
            Drag nodes · Scroll to zoom · Click+drag to pan
          </span>
        </div>
      </div>
    </div>
  );
}