import React from 'react';
import { AbsoluteFill, Img, OffthreadVideo, interpolate, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { Appear, Fade, K, Note, SpeedBadge, Stamp, ease, gothic, klee, mincho, ramp, useT } from './base';
import { GRADE } from './story';
import { LetterFlow } from './tech';

type Z = [number, number, number];   // [倍率, 中心x, 中心y]

export type Overlay =
  | { kind: 'note'; t0: number; t1?: number; x: number; y: number; w?: number; text: string; color?: string; rot?: number; size?: number }
  | { kind: 'stamp'; t0: number; t1?: number; x: number; y: number; text: string; size?: number; rot?: number }
  | { kind: 'timer'; t0: number; t1: number; max: number; x?: number; y?: number; line?: string }
  | { kind: 'letterflow'; t0: number; evals?: { ok: boolean; text: string }[]; tool?: string }
  | { kind: 'count'; t0: number; t1: number; hold?: number; from: number; to: number; x: number; y: number; label: string }
  | { kind: 'corner'; t0: number; t1?: number; text: string; side?: 'left' | 'right' }
  | { kind: 'tap'; t0: number; x: number; y: number };

/** 実際の動作画面(録画)。区間ごとに倍率を変え、早回しのときは右上に倍率を出す */
export const RecScene: React.FC<{ dur: number; src: string; from: number; rate?: number; z0?: Z; z1?: Z; badge?: string; label?: string; overlays?: Overlay[]; dim?: number }> = ({ dur, src, from, rate = 1, z0 = [1, 960, 540], z1, badge, label, overlays = [], dim = 0 }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const zEnd = z1 || z0;
  const p = interpolate(f, [0, dur], [0, 1], { easing: ease, extrapolateRight: 'clamp' });
  const s = z0[0] + (zEnd[0] - z0[0]) * p;
  const cx = z0[1] + (zEnd[1] - z0[1]) * p;
  const cy = z0[2] + (zEnd[2] - z0[2]) * p;
  const tx = Math.min(0, Math.max(1920 - 1920 * s, 960 - cx * s));
  const ty = Math.min(0, Math.max(1080 - 1080 * s, 540 - cy * s));
  return (
    <Fade dur={dur} inF={6} outF={6}>
      <AbsoluteFill style={{ background: '#2b2019', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', left: 0, top: 0, width: 1920, height: 1080, transformOrigin: '0 0', transform: `translate(${tx}px, ${ty}px) scale(${s})` }}>
          <OffthreadVideo src={staticFile(src)} muted trimBefore={Math.round(from * fps)} playbackRate={rate} style={{ width: 1920, height: 1080 }} />
        </div>
        {dim > 0 && <AbsoluteFill style={{ background: `rgba(30,20,12,${dim})` }} />}
        {label && <div style={{ position: 'absolute', left: 44, top: 36, fontFamily: mincho, fontWeight: 500, fontSize: 24, color: K.sumi, background: 'rgba(243,234,216,.88)', padding: '6px 16px', borderRadius: 6, letterSpacing: '0.04em' }}>{label}</div>}
        {badge && <SpeedBadge text={badge} />}
        {overlays.map((o, i) => <OverlayView key={i} o={o} />)}
      </AbsoluteFill>
    </Fade>
  );
};

const OverlayView: React.FC<{ o: Overlay }> = ({ o }) => {
  const t = useT();
  switch (o.kind) {
    case 'note':
      return <Note t0={o.t0} t1={o.t1} x={o.x} y={o.y} w={o.w ?? 460} color={o.color} rot={o.rot} size={o.size ?? 30}>{o.text}</Note>;
    case 'stamp':
      if (o.t1 !== undefined && t > o.t1) return null;
      return <div style={{ position: 'absolute', left: o.x, top: o.y }}><Stamp t0={o.t0} text={o.text} size={o.size ?? 36} rot={o.rot ?? -6} /></div>;
    case 'timer': {
      // 相手が話している時間(推定)を実時間で数える。最後の 0.5 秒は朱に変わる
      if (t < o.t0 - 0.3 || t > o.t1 + 1.2) return null;
      const v = Math.min(o.max, Math.max(0, t - o.t0));
      const done = t >= o.t1 - 0.5;
      const a = ramp(t, o.t0 - 0.3, 0.3) * (1 - ramp(t, o.t1 + 0.6, 0.5));
      return (
        <div style={{ position: 'absolute', left: o.x ?? 1240, top: o.y ?? 150, width: 600, padding: '24px 30px', background: 'rgba(243,234,216,.95)', borderRadius: 14, boxShadow: '0 18px 40px rgba(40,25,10,.3)', opacity: a, fontFamily: mincho }}>
          <div style={{ fontSize: 26, color: K.ai, fontWeight: 800 }}>相手が話している時間(推定)</div>
          <div style={{ fontSize: 130, fontWeight: 800, lineHeight: 1.05, color: done ? K.shu : K.ai, fontVariantNumeric: 'tabular-nums' }}>{v.toFixed(1)}<span style={{ fontSize: 52, marginLeft: 8 }}>秒</span></div>
          <div style={{ height: 14, borderRadius: 7, background: K.aiLight, overflow: 'hidden', marginTop: 6 }}><div style={{ width: `${(v / o.max) * 100}%`, height: '100%', background: done ? K.shu : K.ai }} /></div>
          {o.line && <div style={{ marginTop: 14, fontSize: 28, color: K.sumi, opacity: ramp(t, o.t0 + 1.8, 0.5), lineHeight: 1.45 }}>{o.line}</div>}
        </div>
      );
    }
    case 'count': {
      const h = o.hold ?? 0.2;
      if (t < o.t0 - 0.2 || t > o.t1 + h + 0.4) return null;
      const v = interpolate(t, [o.t0, o.t1], [o.from, o.to], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
      const a = ramp(t, o.t0 - 0.2, 0.2) * (1 - ramp(t, o.t1 + h, 0.4));
      return (
        <div style={{ position: 'absolute', left: o.x, top: o.y, padding: '14px 24px', background: 'rgba(243,234,216,.95)', borderRadius: 12, opacity: a, fontFamily: mincho, color: K.sumi, boxShadow: '0 12px 28px rgba(40,25,10,.25)' }}>
          <span style={{ fontSize: 26 }}>{o.label}</span> <b style={{ fontSize: 54, color: K.ai, fontVariantNumeric: 'tabular-nums' }}>{v.toFixed(0)}</b><span style={{ fontSize: 26 }}> 秒</span>
        </div>
      );
    }
    case 'letterflow':
      return <LetterFlow dur={999} t0={o.t0} evals={o.evals} tool={o.tool} />;
    case 'tap':
      return <Tap t0={o.t0} x={o.x} y={o.y} />;
    case 'corner': {
      const a = ramp(t, o.t0, 0.3) * (o.t1 !== undefined ? 1 - ramp(t, o.t1, 0.3) : 1);
      return <div style={{ position: 'absolute', bottom: 22, [o.side ?? 'right']: 40, fontFamily: mincho, fontSize: 21, color: '#f3ead8', background: 'rgba(30,20,12,.55)', padding: '4px 12px', borderRadius: 4, opacity: a } as React.CSSProperties}>{o.text}</div>;
    }
    default:
      return null;
  }
};

/** 健太の電話のあいだ、勧誘の電話の影(祖母の言葉)が一瞬だけ淡く重なる */
export const Ghost: React.FC<{ t0: number; t1: number; text: string }> = ({ t0, t1, text }) => {
  const t = useT();
  const a = ramp(t, t0, 0.35) * (1 - ramp(t, t1 - 0.4, 0.4));
  if (a <= 0) return null;
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', pointerEvents: 'none' }}>
      <div style={{ fontFamily: klee, fontWeight: 600, fontSize: 58, color: 'rgba(255,240,215,.85)', textShadow: '0 0 28px rgba(255,190,110,.6)', opacity: a * 0.75, transform: `translateY(${-20 * a}px)`, filter: `blur(${(1 - a) * 3}px)` }}>「{text}」</div>
    </AbsoluteFill>
  );
};

/** ふすま一枚(描き起こし): 唐紙(雲の地紋)・黒塗りの縁・丸い引手 */
const FusumaPanel: React.FC<{ side: 'l' | 'r'; shade: number }> = ({ side, shade }) => {
  const kumo = encodeURIComponent(`<svg xmlns='http://www.w3.org/2000/svg' width='220' height='160'><g fill='none' stroke='%23a8925f' stroke-width='2.4' opacity='.55'><path d='M10 60 q 20 -26 44 -8 q 18 -22 40 -4 q 22 -10 30 12 q -24 10 -44 0 q -18 14 -40 2 q -18 10 -30 -2z'/><path d='M120 130 q 16 -20 36 -6 q 14 -18 32 -4 q 18 -8 24 10 q -20 8 -36 0 q -14 12 -32 2 q -14 8 -24 -2z'/></g></svg>`);
  const fiber = encodeURIComponent(`<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 .45  0 0 0 0 .38  0 0 0 0 .28  0 0 0 .5 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>`);
  return (
    <div style={{ position: 'absolute', top: 64, height: 952, width: 960, left: side === 'l' ? 0 : 960 }}>
      <div style={{ position: 'absolute', inset: 0, background: 'repeating-linear-gradient(90deg, #2a1d14 0 3px, #3a281b 3px 7px, #24180f 7px 9px)' }} />
      <div style={{ position: 'absolute', inset: '16px 16px 16px 16px', background: `linear-gradient(${side === 'l' ? '90deg' : '270deg'}, #e9dcc0 0%, #efe4cb 70%, #f4e7c9 100%)` }}>
        <div style={{ position: 'absolute', inset: 0, backgroundImage: `url("data:image/svg+xml;utf8,${kumo}")`, opacity: 0.9 }} />
        <div style={{ position: 'absolute', inset: 0, backgroundImage: `url("data:image/svg+xml;utf8,${fiber}")`, opacity: 0.22, mixBlendMode: 'multiply' }} />
        <div style={{ position: 'absolute', inset: 0, background: `rgba(20,12,6,${shade})` }} />
      </div>
      {/* 引手 */}
      <div style={{ position: 'absolute', top: 452, [side === 'l' ? 'right' : 'left']: 64, width: 34, height: 46, borderRadius: '50%', background: 'radial-gradient(ellipse at 45% 40%, #7a6448 0%, #3f3022 58%, #1f160e 100%)', boxShadow: 'inset 0 2px 5px rgba(0,0,0,.65), 0 0 0 3px rgba(150,120,80,.35), 0 1px 0 rgba(255,240,210,.25)' } as React.CSSProperties} />
    </div>
  );
};

/** 結び: 夕暮れの部屋に、両側からふすまが閉まる。すきまと引手のまわりに、向こうの部屋の灯り。ことばは、ふすまの紙の上に */
export const EndScene: React.FC<{ dur: number; bg: string; closeAt?: number; closeLen?: number; tagAt: number; titleAt: number; repo: string }> = ({ dur, bg, closeAt = 0.2, closeLen = 1.5, tagAt, titleAt, repo }) => {
  const f = useCurrentFrame();
  const t = useT();
  const close = ramp(t, closeAt, closeLen);
  const z = interpolate(f, [0, dur], [1.1, 1.0], { extrapolateRight: 'clamp' });
  const warm = ramp(t, closeAt + closeLen * 0.8, 2.2);
  const gap = 4;
  const shade = 0.18 + 0.12 * ramp(t, titleAt, 1.5);
  return (
    <Fade dur={dur} inF={8} outF={2}>
      <AbsoluteFill style={{ background: '#0b0806', overflow: 'hidden' }}>
        <AbsoluteFill style={{ transform: `scale(${z})` }}>
          <Img src={staticFile(bg)} style={{ width: '100%', height: '100%', objectFit: 'cover', filter: `${GRADE.dusk} brightness(.75)` }} />
          {/* 鴨居と敷居 */}
          <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: 66, background: 'linear-gradient(#2a1d14, #3b2a1d)', opacity: close }} />
          <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 66, background: 'linear-gradient(#3b2a1d, #20160f)', opacity: close }} />
          <div style={{ position: 'absolute', inset: 0, transform: `translateX(${-(1 - close) * 980 - gap / 2}px)` }}><FusumaPanel side="l" shade={shade} /></div>
          <div style={{ position: 'absolute', inset: 0, transform: `translateX(${(1 - close) * 980 + gap / 2}px)` }}><FusumaPanel side="r" shade={shade} /></div>
          {/* すきまの灯り */}
          <div style={{ position: 'absolute', left: 960 - 2, top: 64, width: 4, height: 952, background: 'rgba(255,214,150,.95)', filter: 'blur(1px)', opacity: warm }} />
          <div style={{ position: 'absolute', left: 960 - 60, top: 64, width: 120, height: 952, background: 'linear-gradient(90deg, rgba(255,180,90,0), rgba(255,196,120,.45) 50%, rgba(255,180,90,0))', filter: 'blur(8px)', mixBlendMode: 'screen', opacity: warm }} />
          <AbsoluteFill style={{ background: `radial-gradient(700px 520px at 960px 470px, rgba(255,176,90,${0.18 * warm}), transparent 70%)`, mixBlendMode: 'screen' }} />
          <AbsoluteFill style={{ background: 'radial-gradient(ellipse at center, transparent 45%, rgba(8,5,3,.55) 100%)' }} />
        </AbsoluteFill>
        <Appear t0={tagAt} dy={8} style={{ position: 'absolute', left: 0, right: 0, top: 250, textAlign: 'center' }}>
          <div style={{ fontFamily: mincho, fontWeight: 800, fontSize: 84, color: '#2a2018', letterSpacing: '0.18em', textShadow: '0 1px 0 rgba(255,245,225,.35)' }}>閉めたままで、そばにいる。</div>
        </Appear>
        <Appear t0={titleAt} dy={6} style={{ position: 'absolute', left: 0, right: 0, top: 640, textAlign: 'center' }}>
          <div style={{ fontFamily: mincho, fontWeight: 800, fontSize: 66, color: '#7a2e1f', letterSpacing: '0.34em' }}>ふすまごし</div>
          <div style={{ fontFamily: gothic, fontSize: 25, color: '#3a2c20', marginTop: 26, letterSpacing: '0.08em' }}>Built with Claude: Japan 2026{repo ? `　・　${repo}` : ''}</div>
          <div style={{ fontFamily: gothic, fontSize: 19, color: '#5a4a3a', marginTop: 12 }}>通話はすべて架空の台本、声は合成音声です。人物・会社は架空です。</div>
        </Appear>
      </AbsoluteFill>
    </Fade>
  );
};

/** 画面を押す(親指のかわりに、波紋) */
export const Tap: React.FC<{ t0: number; x: number; y: number }> = ({ t0, x, y }) => {
  const t = useT();
  const p = ramp(t, t0, 0.5);
  if (t < t0 || p >= 1) return null;
  return <div style={{ position: 'absolute', left: x - 60 * p - 20, top: y - 60 * p - 20, width: 40 + 120 * p, height: 40 + 120 * p, borderRadius: '50%', border: '4px solid rgba(255,248,235,.9)', opacity: 1 - p, boxShadow: '0 0 20px rgba(255,220,170,.6)' }} />;
};

/** 字幕(明朝。話し手の名前つき) */
export const Captions2: React.FC<{ items: { start: number; end: number; text: string; who?: string; size?: number }[] }> = ({ items }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = f / fps;
  const cur = items.filter((c) => t >= c.start && t < c.end);
  if (!cur.length) return null;
  const c = cur[cur.length - 1];
  const o = Math.min(interpolate(t, [c.start, c.start + 0.15], [0, 1], { extrapolateRight: 'clamp' }), interpolate(t, [c.end - 0.15, c.end], [1, 0], { extrapolateLeft: 'clamp' }));
  const who = c.who && c.who !== 'narr' ? ({ grandma: '祖母', fusuma: 'ふすまごし', kenta: '健太' } as Record<string, string>)[c.who] : null;
  const col = c.who === 'grandma' ? '#d9ecd9' : c.who === 'fusuma' ? '#f6cf8a' : c.who === 'kenta' ? '#cfdcf2' : '#fff';
  return (
    <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 54, pointerEvents: 'none' }}>
      <div style={{ opacity: o, maxWidth: 1560, background: 'rgba(22,15,10,.62)', borderRadius: 10, padding: '12px 30px 14px', fontFamily: mincho, fontWeight: 500, fontSize: c.size ?? 44, lineHeight: 1.5, color: '#fbf6ec', textAlign: 'center', whiteSpace: 'pre-line', letterSpacing: '0.03em', textShadow: '0 1px 2px rgba(0,0,0,.4)', textWrap: 'balance' } as React.CSSProperties}>
        {who && <span style={{ fontFamily: mincho, fontWeight: 800, fontSize: 26, color: col, marginRight: 18, verticalAlign: 'middle', letterSpacing: '0.08em' }}>{who}</span>}
        {c.text}
      </div>
    </AbsoluteFill>
  );
};

/** ふすまが開く/閉まる(写真を左右に割って、すっと引く)。下の場面の上に重ねる */
export const FusumaSlide: React.FC<{ dur: number; src: string; mode: 'open' | 'close'; at?: number; len?: number; grade?: string }> = ({ dur, src, mode, at = 0, len = 0.75, grade = 'warm' }) => {
  const t = useT();
  const p = mode === 'open' ? ramp(t, at, len) : 1 - ramp(t, at, len);
  if (mode === 'open' && p >= 1) return null;
  if (mode === 'close' && t < at - 0.01) return null;
  if (src === 'drawn') {   // 結びと同じ、描き起こしのふすま(鴨居と敷居つき)
    return (
      <AbsoluteFill style={{ pointerEvents: 'none' }}>
        <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: 66, background: 'linear-gradient(#2a1d14, #3b2a1d)', opacity: 1 - p }} />
        <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 66, background: 'linear-gradient(#3b2a1d, #20160f)', opacity: 1 - p }} />
        <div style={{ position: 'absolute', inset: 0, transform: `translateX(${-p * 980 - 2}px)` }}><FusumaPanel side="l" shade={0.12} /></div>
        <div style={{ position: 'absolute', inset: 0, transform: `translateX(${p * 980 + 2}px)` }}><FusumaPanel side="r" shade={0.12} /></div>
      </AbsoluteFill>
    );
  }
  const half = (side: 'l' | 'r') => (
    <div style={{ position: 'absolute', top: 0, height: 1080, width: 960, left: side === 'l' ? 0 : 960, overflow: 'hidden', transform: `translateX(${(side === 'l' ? -1 : 1) * p * 980}px)`, boxShadow: side === 'l' ? '12px 0 30px rgba(0,0,0,.35)' : '-12px 0 30px rgba(0,0,0,.35)' }}>
      <Img src={staticFile(src)} style={{ position: 'absolute', top: 0, left: side === 'l' ? 0 : -960, width: 1920, height: 1080, objectFit: 'cover', filter: GRADE[grade] ?? grade }} />
      <div style={{ position: 'absolute', top: 470, [side === 'l' ? 'right' : 'left']: 40, width: 26, height: 120, borderRadius: 13, background: 'radial-gradient(circle at 40% 40%, #6b5a48, #2d241c)', opacity: 0.85 } as React.CSSProperties} />
    </div>
  );
  return <AbsoluteFill style={{ pointerEvents: 'none' }}>{half('l')}{half('r')}</AbsoluteFill>;
};
