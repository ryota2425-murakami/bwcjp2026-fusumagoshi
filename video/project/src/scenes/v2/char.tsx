import React from 'react';
import { AbsoluteFill, OffthreadVideo, interpolate, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { gothic } from './base';

/* Claude のキャラ(HyperFrames で透過つきに書き出した映像)を、場面の上に重ねる。
   src: public/ からのパス(ProRes 4444 の .mov / VP9 alpha の .webm)
   x, y, w: 置く位置と幅(1920×1080 の座標)、panel: Pi の画面のような角丸の枠に入れる、label: 枠の下の小さな説明 */
export const CharOverlay: React.FC<{ dur: number; src: string; from?: number; rate?: number; x?: number; y?: number; w?: number; h?: number;
  panel?: boolean; label?: string; sub?: string; note?: string; fadeIn?: number; fadeOut?: number; rise?: boolean; cardBottom?: number }> = ({ dur, src, from = 0, rate = 1, x = 0, y = 0, w = 1920, h, panel, label, sub, note, fadeIn = 0.25, fadeOut = 0.25, rise: doRise = true, cardBottom }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const hh = h ?? Math.round(w * 9 / 16);
  const fi = fadeIn > 0 ? interpolate(f, [0, fadeIn * fps], [0, 1], { extrapolateRight: 'clamp' }) : 1;
  const fo = fadeOut > 0 ? interpolate(f, [dur - fadeOut * fps, dur], [1, 0], { extrapolateLeft: 'clamp' }) : 1;
  const op = Math.min(fi, fo);
  const rise = doRise && fadeIn >= 0.1 ? interpolate(f, [0, fadeIn * fps * 1.6], [18, 0], { extrapolateRight: 'clamp' }) : 0;   // 切り替えの途中では動かさない
  const isAlpha = /\.(mov|webm)$/i.test(src);
  const video = <OffthreadVideo src={staticFile(src)} transparent={isAlpha} muted trimBefore={Math.round(from * fps)} playbackRate={rate} style={{ width: '100%', height: '100%', display: 'block' }} />;
  if (!panel) {
    return <AbsoluteFill style={{ opacity: op }}><div style={{ position: 'absolute', left: x, top: y + rise, width: w, height: hh }}>{video}</div></AbsoluteFill>;
  }
  // Pi の画面の小窓: 暗い台紙に、画面と説明(見出し + ひとこと)をまとめる。下の画面の文字と重ならないように
  const pad = 16;
  return (
    <AbsoluteFill style={{ opacity: op }}>
      <div style={{ position: 'absolute', left: x - pad, top: y - pad + rise, width: w + pad * 2, padding: pad, boxSizing: 'border-box', borderRadius: 26,
        minHeight: cardBottom ? cardBottom - (y - pad) : undefined,
        background: '#211a15', boxShadow: '0 18px 44px rgba(30, 18, 8, .38)' }}>
        <div style={{ width: w, height: hh, borderRadius: 14, overflow: 'hidden', boxShadow: 'inset 0 0 0 1px rgba(255,255,255,.08)' }}>{video}</div>
        {label && <div style={{ marginTop: 12, fontFamily: gothic, fontSize: 26, fontWeight: 700, color: '#f6efe4', letterSpacing: '0.02em' }}>{label}</div>}
        {sub && <div style={{ marginTop: 4, fontFamily: gothic, fontSize: 21, color: '#d9cbb8', lineHeight: 1.4 }}>{sub}</div>}
        {note && <div style={{ marginTop: 14, paddingTop: 10, borderTop: '1px solid rgba(255,255,255,.12)', fontFamily: gothic, fontSize: 19, color: '#b9ab97', lineHeight: 1.5 }}>{note}</div>}
      </div>
    </AbsoluteFill>
  );
};
