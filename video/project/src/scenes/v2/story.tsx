import React from 'react';
import { AbsoluteFill, Img, OffthreadVideo, interpolate, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { Corner, Fade, K, mincho, ramp, useT } from './base';

/** 時間帯ごとの色(夕方・昼・夜・色を抜いた昼) */
export const GRADE: Record<string, string> = {
  dusk: 'sepia(.18) saturate(1.05) brightness(.92) contrast(1.04)',
  day: 'saturate(.9) brightness(1.0) contrast(1.02)',
  pale: 'saturate(.55) brightness(1.02) contrast(.98) sepia(.08)',
  night: 'saturate(.8) brightness(.78) contrast(1.06) hue-rotate(-8deg)',
  warm: 'sepia(.22) saturate(1.1) brightness(.96)',
};

type Note = { t0: number; t1?: number; text: string; side?: 'left' | 'right' };

/** 写真を、ゆっくり寄りながら見せる。fromBlack で黒から浮かぶ。seam でふすまのすきまの灯り */
export const PhotoKB: React.FC<{
  dur: number; src: string; grade?: string; z0?: number; z1?: number; x0?: number; y0?: number; x1?: number; y1?: number;
  fromBlack?: number; seam?: { x: number; y0: number; y1: number; t0?: number }; beam?: { x0: number; y0: number; x1: number; y1: number; t0?: number };
  notes?: Note[]; vignette?: number;
}> = ({ dur, src, grade = 'dusk', z0 = 1.04, z1 = 1.12, x0 = 0, y0 = 0, x1, y1, fromBlack = 0, seam, beam, notes = [], vignette = 0.55 }) => {
  const f = useCurrentFrame();
  const t = useT();
  const p = interpolate(f, [0, dur], [0, 1]);
  const z = z0 + (z1 - z0) * p;
  const x = x0 + ((x1 ?? x0) - x0) * p;
  const y = y0 + ((y1 ?? y0) - y0) * p;
  const black = fromBlack ? 1 - ramp(t, fromBlack * 0.6, fromBlack) : 0;
  return (
    <Fade dur={dur} inF={fromBlack ? 1 : 10}>
      <AbsoluteFill style={{ background: '#0c0a08', overflow: 'hidden' }}>
        <Img src={staticFile(src)} style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${z}) translate(${x}px, ${y}px)`, filter: GRADE[grade] ?? grade }} />
        {seam && (
          <div style={{ position: 'absolute', left: seam.x - 30, top: seam.y0, width: 60, height: seam.y1 - seam.y0, opacity: 0.55 + 0.45 * ramp(t, seam.t0 ?? 0, 2.5),
            background: 'linear-gradient(90deg, rgba(255,190,110,0) 0%, rgba(255,198,120,.85) 50%, rgba(255,190,110,0) 100%)', filter: 'blur(6px)', mixBlendMode: 'screen' }} />
        )}
        {beam && (
          <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0, mixBlendMode: 'screen', opacity: ramp(t, beam.t0 ?? 1.5, 2.5) }}>
            <defs><linearGradient id="bm" x1="0" x2="1"><stop offset="0" stopColor="rgba(255,200,120,.0)" /><stop offset=".3" stopColor="rgba(255,205,130,.75)" /><stop offset="1" stopColor="rgba(255,200,120,.0)" /></linearGradient></defs>
            <line x1={beam.x0} y1={beam.y0} x2={beam.x1} y2={beam.y1} stroke="url(#bm)" strokeWidth={7} style={{ filter: 'blur(2px)' }} />
          </svg>
        )}
        <AbsoluteFill style={{ background: `radial-gradient(ellipse at center, transparent 45%, rgba(15,8,4,${vignette}) 100%)` }} />
        {notes.map((n, i) => <Corner key={i} {...n} />)}
        <AbsoluteFill style={{ background: '#000', opacity: black }} />
      </AbsoluteFill>
    </Fade>
  );
};

/** 実写の動画(色をそろえ、ゆっくり寄る) */
export const VideoKB: React.FC<{ dur: number; src: string; from?: number; rate?: number; grade?: string; z0?: number; z1?: number; x?: number; notes?: Note[]; callEnd?: { t0: number } }> = ({ dur, src, from = 0, rate = 1, grade = 'day', z0 = 1.02, z1 = 1.08, x = 0, notes = [], callEnd }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = useT();
  const z = z0 + (z1 - z0) * interpolate(f, [0, dur], [0, 1]);
  return (
    <Fade dur={dur}>
      <AbsoluteFill style={{ background: '#000', overflow: 'hidden' }}>
        <OffthreadVideo src={staticFile(src)} startFrom={Math.round(from * fps)} playbackRate={rate} muted style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${z}) translate(${x}px, 0px)`, filter: GRADE[grade] ?? grade }} />
        <AbsoluteFill style={{ background: 'radial-gradient(ellipse at center, transparent 50%, rgba(10,6,4,.55) 100%)' }} />
        {callEnd && (
          <div style={{ position: 'absolute', left: 760, top: 300, width: 400, padding: '30px 0', borderRadius: 36, background: 'rgba(20,18,16,.72)', color: '#f3ead8', textAlign: 'center', fontFamily: mincho, opacity: ramp(t, callEnd.t0, 0.3) * (1 - ramp(t, callEnd.t0 + 2.2, 0.4)) }}>
            <div style={{ fontSize: 44, fontWeight: 800 }}>ばあちゃん</div>
            <div style={{ fontSize: 26, marginTop: 10, color: '#d9cdb8' }}>{t < callEnd.t0 + 1.1 ? '通話中 3:12' : '通話終了'}</div>
          </div>
        )}
        {notes.map((n, i) => <Corner key={i} {...n} />)}
      </AbsoluteFill>
    </Fade>
  );
};

/** 黒い画面(音だけ) */
export const Black: React.FC<{ dur: number }> = () => <AbsoluteFill style={{ background: '#000' }} />;

export { K };
