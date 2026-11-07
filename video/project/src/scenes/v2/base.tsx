import React from 'react';
import { AbsoluteFill, Easing, interpolate, random, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { K, klee, mincho, gothic } from '../../theme';

export const ease = Easing.bezier(0.33, 0, 0.2, 1);

/** 場面の中の時間を、区間ごとに伸び縮みさせる(図の振り付けをナレーションの位置に合わせる)。map は [実際の秒, 図の秒] の組 */
const WarpCtx = React.createContext<((t: number) => number) | null>(null);
export const Warp: React.FC<{ map?: [number, number][]; children: React.ReactNode }> = ({ map, children }) => {
  const fn = map && map.length > 1 ? (t: number) => {
    for (let i = 0; i < map.length - 1; i++) {
      const [a0, b0] = map[i], [a1, b1] = map[i + 1];
      if (t <= a1) return b0 + ((t - a0) * (b1 - b0)) / Math.max(1e-6, a1 - a0);
    }
    const [aL, bL] = map[map.length - 1];
    return bL + (t - aL);
  } : null;
  return <WarpCtx.Provider value={fn}>{children}</WarpCtx.Provider>;
};

/** 経過秒(Warp の中では、図の秒) */
export const useT = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const w = React.useContext(WarpCtx);
  return w ? w(f / fps) : f / fps;
};

/** t0 から dur 秒かけて 0→1(以後 1) */
export const ramp = (t: number, t0: number, dur = 0.5) =>
  interpolate(t, [t0, t0 + dur], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease });

/** 和紙(繊維の粒と、ゆるい明暗) */
export const Paper: React.FC<{ tone?: number; children?: React.ReactNode }> = ({ tone = 1, children }) => {
  const f = useCurrentFrame();
  const fibers = encodeURIComponent(
    `<svg xmlns='http://www.w3.org/2000/svg' width='320' height='320'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='3' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 .45  0 0 0 0 .38  0 0 0 0 .3  0 0 0 .5 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>`,
  );
  const x = Math.floor(random(`px${Math.floor(f / 3)}`) * 40);
  return (
    <AbsoluteFill style={{ background: `radial-gradient(1400px 900px at 30% 20%, #f8f1e2 0%, ${K.washi} 55%, ${K.washi2} 100%)`, fontFamily: mincho, color: K.sumi, filter: `brightness(${tone})` }}>
      <AbsoluteFill style={{ backgroundImage: `url("data:image/svg+xml;utf8,${fibers}")`, backgroundPosition: `${x}px 0`, opacity: 0.18, mixBlendMode: 'multiply' }} />
      {children}
    </AbsoluteFill>
  );
};

export const Fade: React.FC<{ dur: number; inF?: number; outF?: number; children: React.ReactNode }> = ({ dur, inF = 10, outF = 10, children }) => {
  const f = useCurrentFrame();
  const o = Math.min(interpolate(f, [0, inF], [0, 1], { extrapolateRight: 'clamp' }), interpolate(f, [dur - outF, dur], [1, 0], { extrapolateLeft: 'clamp' }));
  return <AbsoluteFill style={{ opacity: o }}>{children}</AbsoluteFill>;
};

/** 出てくる文字(ふわっと上がる) */
export const Appear: React.FC<{ t0: number; t1?: number; dy?: number; style?: React.CSSProperties; children: React.ReactNode }> = ({ t0, t1, dy = 14, style, children }) => {
  const t = useT();
  const a = ramp(t, t0, 0.45) * (t1 !== undefined ? 1 - ramp(t, t1, 0.35) : 1);
  return <div style={{ opacity: a, transform: `translateY(${(1 - ramp(t, t0, 0.45)) * dy}px)`, ...style }}>{children}</div>;
};

/** 朱の判(押すときに少し縮む) */
export const Stamp: React.FC<{ t0: number; text: string; size?: number; rot?: number; color?: string; style?: React.CSSProperties }> = ({ t0, text, size = 34, rot = -8, color = K.shu, style }) => {
  const t = useT();
  const { fps } = useVideoConfig();
  const s = spring({ frame: (t - t0) * fps, fps, config: { damping: 11, mass: 0.6 } });
  if (t < t0) return null;
  return (
    <div style={{ display: 'inline-block', transform: `rotate(${rot}deg) scale(${1.25 - 0.25 * s})`, opacity: Math.min(1, s * 1.4), ...style }}>
      <div style={{ border: `${size * 0.09}px solid ${color}`, color, borderRadius: size * 0.18, padding: `${size * 0.12}px ${size * 0.38}px`, fontFamily: mincho, fontWeight: 800, fontSize: size, letterSpacing: '0.06em', lineHeight: 1.2, background: 'rgba(196,67,44,.04)', boxShadow: `inset 0 0 0 ${size * 0.04}px rgba(196,67,44,.25)` }}>{text}</div>
    </div>
  );
};

/** 郵便の消印(時刻と場面) */
export const Postmark: React.FC<{ t0: number; time: string; label: string; x?: number; y?: number }> = ({ t0, time, label, x = 1600, y = 840 }) => {
  const t = useT();
  const a = ramp(t, t0, 0.25);
  return (
    <div style={{ position: 'absolute', left: x, top: y, width: 230, height: 230, borderRadius: '50%', border: `5px solid ${K.shu}`, color: K.shu, opacity: a * 0.9, transform: `rotate(-12deg) scale(${1.2 - 0.2 * a})`, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', fontFamily: mincho }}>
      <div style={{ fontSize: 46, fontWeight: 800, letterSpacing: '0.04em' }}>{time}</div>
      <div style={{ width: 170, borderTop: `3px solid ${K.shu}`, margin: '6px 0' }} />
      <div style={{ fontSize: 22, fontWeight: 800, textAlign: 'center', lineHeight: 1.3, padding: '0 18px' }}>{label}</div>
    </div>
  );
};

/** 早回しの倍率(右上) */
export const SpeedBadge: React.FC<{ text: string }> = ({ text }) => (
  <div style={{ position: 'absolute', right: 56, top: 46, padding: '10px 22px', borderRadius: 999, background: 'rgba(243,234,216,.92)', border: `2px solid ${K.sumi}`, fontFamily: gothic, fontWeight: 500, fontSize: 30, color: K.sumi, letterSpacing: '0.04em' }}>{text}</div>
);

/** 手書きの札(付箋) */
export const Note: React.FC<{ t0: number; t1?: number; x: number; y: number; w?: number; children: React.ReactNode; color?: string; rot?: number; size?: number }> = ({ t0, t1, x, y, w = 420, children, color = '#fff7d6', rot = -1.5, size = 30 }) => {
  const t = useT();
  const a = ramp(t, t0, 0.3) * (t1 !== undefined ? 1 - ramp(t, t1, 0.3) : 1);
  return (
    <div style={{ position: 'absolute', left: x, top: y, width: w, padding: '16px 22px', background: color, boxShadow: '0 10px 24px rgba(60,40,20,.18)', transform: `rotate(${rot}deg) translateY(${(1 - a) * 10}px)`, opacity: a, fontFamily: klee, fontWeight: 600, fontSize: size, color: K.sumi, lineHeight: 1.45 }}>
      {children}
    </div>
  );
};

/** 墨で引く線(長さに合わせて描かれる) */
export const InkPath: React.FC<{ d: string; t0: number; dur?: number; width?: number; color?: string; len?: number; dash?: string }> = ({ d, t0, dur = 0.6, width = 4, color = K.sumi, len = 2000, dash }) => {
  const t = useT();
  const p = ramp(t, t0, dur);
  return <path d={d} fill="none" stroke={color} strokeWidth={width} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={dash ?? `${len}`} strokeDashoffset={dash ? 0 : len * (1 - p)} opacity={dash ? p : 1} />;
};

/** 小さな注記(左下・右下) */
export const Corner: React.FC<{ t0: number; t1?: number; text: string; side?: 'left' | 'right'; dark?: boolean }> = ({ t0, t1, text, side = 'left', dark }) => {
  const t = useT();
  const a = ramp(t, t0, 0.4) * (t1 !== undefined ? 1 - ramp(t, t1, 0.4) : 1);
  return <div style={{ position: 'absolute', bottom: 210, [side]: 70, fontFamily: mincho, fontWeight: 500, fontSize: 30, color: dark ? K.sumi : '#f6efe2', opacity: a * 0.95, letterSpacing: '0.06em', textShadow: dark ? 'none' : '0 2px 14px rgba(0,0,0,.55)' } as React.CSSProperties}>{text}</div>;
};

export { K, klee, mincho, gothic };
