import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig, random } from 'remotion';
import { C, maru } from '../theme';

/** 和紙の背景(ゆっくり揺れる光) */
export const Washi: React.FC<{ dark?: boolean; children?: React.ReactNode }> = ({ dark, children }) => (
  <AbsoluteFill style={{
    background: dark
      ? `radial-gradient(1200px 700px at 75% 20%, #2b3550 0%, transparent 60%), radial-gradient(900px 700px at 10% 90%, #3a2b25 0%, transparent 55%), ${C.night}`
      : `radial-gradient(1200px 700px at 12% -10%, #fff7e6 0%, transparent 60%), radial-gradient(900px 600px at 110% 10%, #f1e6d3 0%, transparent 55%), ${C.kinari}`,
    fontFamily: maru,
  }}>
    <Grain opacity={dark ? 0.08 : 0.09} />
    {children}
  </AbsoluteFill>
);

/** フィルムの粒子(フレームごとに位置をずらしてちらつかせる) */
export const Grain: React.FC<{ opacity?: number }> = ({ opacity = 0.2 }) => {
  const f = useCurrentFrame();
  const x = Math.floor(random(`gx${Math.floor(f / 2)}`) * 160);
  const y = Math.floor(random(`gy${Math.floor(f / 2)}`) * 160);
  const svg = encodeURIComponent(
    `<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 .5  0 0 0 0 .42  0 0 0 0 .33  0 0 0 .55 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>`,
  );
  return <AbsoluteFill style={{ backgroundImage: `url("data:image/svg+xml;utf8,${svg}")`, backgroundPosition: `${x}px ${y}px`, opacity, mixBlendMode: 'multiply', pointerEvents: 'none' }} />;
};

export const Vignette: React.FC<{ strength?: number }> = ({ strength = 0.55 }) => (
  <AbsoluteFill style={{ background: `radial-gradient(ellipse at center, transparent 45%, rgba(20,12,6,${strength}) 100%)`, pointerEvents: 'none' }} />
);

/** 場面の入り・終わりのフェード */
export const Fade: React.FC<{ dur: number; inF?: number; outF?: number; children: React.ReactNode }> = ({ dur, inF = 12, outF = 12, children }) => {
  const f = useCurrentFrame();
  const o = Math.min(interpolate(f, [0, inF], [0, 1], { extrapolateRight: 'clamp' }), interpolate(f, [dur - outF, dur], [1, 0], { extrapolateLeft: 'clamp' }));
  return <AbsoluteFill style={{ opacity: o }}>{children}</AbsoluteFill>;
};

export const Chip: React.FC<{ children: React.ReactNode; color?: string; bg?: string; size?: number }> = ({ children, color = '#fff', bg = C.sumi, size = 22 }) => (
  <span style={{ display: 'inline-block', padding: `${size * 0.32}px ${size * 0.8}px`, borderRadius: 999, background: bg, color, fontSize: size, fontWeight: 700, letterSpacing: '0.06em' }}>{children}</span>
);

export const useSec = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return f / fps;
};
