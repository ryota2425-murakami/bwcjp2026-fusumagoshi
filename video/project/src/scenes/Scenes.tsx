import React from 'react';
import { AbsoluteFill, Img, OffthreadVideo, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig, Easing } from 'remotion';
import { C, maru, klee } from '../theme';
import { Chip, Fade, Grain, Vignette, Washi } from './common';

const ease = Easing.bezier(0.33, 0, 0.2, 1);

const filterOf = (f?: string) =>
  f === 'sepia' ? 'sepia(0.55) saturate(0.8) contrast(1.06) brightness(0.9)'
    : f === 'warm' ? 'sepia(0.25) saturate(0.95) brightness(0.95)'
      : f === 'night' ? 'saturate(0.9) brightness(0.85)' : 'none';

// ---------------------------------------------------------------- 実写の写真(ゆっくり寄る)
export const PhotoScene: React.FC<{ dur: number; src: string; filter?: string; zoomFrom?: number; zoomTo?: number; x?: number; y?: number; title?: string }> = ({ dur, src, filter, zoomFrom = 1.04, zoomTo = 1.16, x = 0, y = 0, title }) => {
  const f = useCurrentFrame();
  const s = interpolate(f, [0, dur], [zoomFrom, zoomTo], { easing: ease });
  return (
    <Fade dur={dur} inF={18} outF={14}>
      <AbsoluteFill style={{ background: '#000', overflow: 'hidden' }}>
        <Img src={staticFile(src)} style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${s}) translate(${x * (s - 1) * 100}px, ${y * (s - 1) * 100}px)`, filter: filterOf(filter) }} />
        {filter === 'sepia' && <Grain opacity={0.28} />}
        <Vignette strength={filter === 'sepia' ? 0.6 : 0.35} />
        {title && <div style={{ position: 'absolute', left: 120, top: 110, fontFamily: maru, color: '#fff', fontSize: 30, letterSpacing: '0.2em', opacity: 0.85, textShadow: '0 2px 12px rgba(0,0,0,.5)' }}>{title}</div>}
      </AbsoluteFill>
    </Fade>
  );
};

// ---------------------------------------------------------------- 実写の動画
export const VideoScene: React.FC<{ dur: number; src: string; from?: number; rate?: number; filter?: string; zoom?: number; title?: string }> = ({ dur, src, from = 0, rate = 1, filter, zoom = 1.0, title }) => {
  const { fps } = useVideoConfig();
  const f = useCurrentFrame();
  const s = interpolate(f, [0, dur], [zoom, zoom * 1.05]);
  return (
    <Fade dur={dur} inF={14} outF={14}>
      <AbsoluteFill style={{ background: '#000', overflow: 'hidden' }}>
        <OffthreadVideo src={staticFile(src)} muted trimBefore={Math.round(from * fps)} playbackRate={rate}
          style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${s})`, filter: filterOf(filter) }} />
        {filter === 'sepia' && <Grain opacity={0.26} />}
        <Vignette strength={filter === 'sepia' ? 0.6 : 0.4} />
        {title && <div style={{ position: 'absolute', left: 120, top: 110, fontFamily: maru, color: '#fff', fontSize: 30, letterSpacing: '0.2em', opacity: 0.9, textShadow: '0 2px 12px rgba(0,0,0,.6)' }}>{title}</div>}
      </AbsoluteFill>
    </Fade>
  );
};

// ---------------------------------------------------------------- 数字のカード
export const StatsScene: React.FC<{ dur: number; title: string; items: { num: string; unit: string; label: string; source: string }[] }> = ({ dur, title, items }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <Fade dur={dur}>
      <Washi>
        <div style={{ position: 'absolute', left: 140, top: 150, fontSize: 46, fontWeight: 900, color: C.sumi, letterSpacing: '0.06em' }}>{title}</div>
        <div style={{ position: 'absolute', left: 140, right: 140, top: 290, display: 'flex', gap: 40 }}>
          {items.map((it, i) => {
            const sp = spring({ frame: f - 8 - i * 9, fps, config: { damping: 14 } });
            return (
              <div key={i} style={{ flex: 1, background: C.paper, borderRadius: 34, padding: '44px 40px', boxShadow: '0 14px 40px rgba(84,56,30,.12)', transform: `translateY(${(1 - sp) * 40}px)`, opacity: sp }}>
                <div style={{ fontSize: 24, color: C.sumi2, fontWeight: 700, minHeight: 64, lineHeight: 1.35 }}>{it.label}</div>
                <div style={{ marginTop: 18, color: C.sumi }}><span style={{ fontSize: 96, fontWeight: 900, letterSpacing: '-0.02em' }}>{it.num}</span><span style={{ fontSize: 34, fontWeight: 700, marginLeft: 6 }}>{it.unit}</span></div>
                <div style={{ marginTop: 18, fontSize: 18, color: C.sumi3 }}>{it.source}</div>
              </div>
            );
          })}
        </div>
      </Washi>
    </Fade>
  );
};

// ---------------------------------------------------------------- タイトル(行灯が灯る)
const Andon: React.FC<{ glow: number; size?: number }> = ({ glow, size = 1 }) => (
  <div style={{ width: 230 * size, position: 'relative', filter: `drop-shadow(0 30px 40px rgba(160,90,20,${0.15 + glow * 0.35}))` }}>
    <div style={{ position: 'absolute', left: -120 * size, right: -120 * size, top: 40 * size, height: 320 * size, borderRadius: '50%', background: 'radial-gradient(closest-side, rgba(255,214,130,.55), rgba(255,214,130,0))', opacity: glow }} />
    <div style={{ height: 18 * size, borderRadius: 10, background: 'linear-gradient(#a06c48,#7a4c30)', margin: `0 ${-12 * size}px`, position: 'relative' }} />
    <div style={{ height: 290 * size, margin: `0 ${8 * size}px`, position: 'relative', overflow: 'hidden', borderLeft: `${8 * size}px solid ${C.wood}`, borderRight: `${8 * size}px solid ${C.wood}`, background: '#efe6d4' }}>
      <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(60% 55% at 50% 55%, #fff3cf 0%, #ffd98a 38%, #f3b562 70%, #e2a25a 100%)', opacity: glow }} />
      <div style={{ position: 'absolute', inset: 0, background: `repeating-linear-gradient(90deg, transparent 0 ${64 * size}px, rgba(138,90,59,.55) ${64 * size}px ${68 * size}px), repeating-linear-gradient(0deg, transparent 0 ${92 * size}px, rgba(138,90,59,.55) ${92 * size}px ${96 * size}px)` }} />
    </div>
    <div style={{ height: 18 * size, borderRadius: 10, background: 'linear-gradient(#a06c48,#7a4c30)', margin: `0 ${-12 * size}px` }} />
  </div>
);

export const TitleScene: React.FC<{ dur: number }> = ({ dur }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const glow = interpolate(f, [10, 60], [0.05, 0.85], { extrapolateRight: 'clamp', extrapolateLeft: 'clamp' });
  const chips = ['通話中は、光らない・話さない', '聞くのは、祖母の声だけ', '話しかけるのは、電話のあと'];
  return (
    <Fade dur={dur} inF={16}>
      <Washi>
        <div style={{ position: 'absolute', left: 230, top: 250 }}><Andon glow={glow} /></div>
        <div style={{ position: 'absolute', left: 640, top: 270 }}>
          {'ふすまごし'.split('').map((ch, i) => {
            const sp = spring({ frame: f - 20 - i * 5, fps, config: { damping: 12 } });
            return <span key={i} style={{ display: 'inline-block', fontSize: 150, fontWeight: 900, color: C.sumi, letterSpacing: '0.08em', transform: `translateY(${(1 - sp) * 30}px)`, opacity: sp }}>{ch}</span>;
          })}
          <div style={{ fontSize: 40, color: C.sumi2, marginTop: 10, letterSpacing: '0.12em', opacity: interpolate(f, [50, 70], [0, 1], { extrapolateRight: 'clamp', extrapolateLeft: 'clamp' }) }}>離れていても、ふすま一枚向こうに。</div>
          <div style={{ display: 'flex', gap: 18, marginTop: 56, flexWrap: 'wrap', maxWidth: 1100 }}>
            {chips.map((c, i) => {
              const sp = spring({ frame: f - 150 - i * 10, fps, config: { damping: 14 } });
              return <span key={i} style={{ opacity: sp, transform: `scale(${0.9 + sp * 0.1})` }}><Chip size={26} bg={i === 0 ? C.ai : i === 1 ? C.wakatake : C.shu}>{c}</Chip></span>;
            })}
          </div>
        </div>
      </Washi>
    </Fade>
  );
};

// ---------------------------------------------------------------- 実際の画面(録画)をカメラで寄って見せる
export const ScreenScene: React.FC<{ dur: number; src: string; from: number; rate?: number; z0?: number[]; z1?: number[]; badge?: string; label?: string; dim?: number }> = ({ dur, src, from, rate = 1, z0 = [1, 960, 540], z1, badge, label = '実際の動作画面' }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const zEnd = z1 || z0;
  const t = interpolate(f, [0, dur], [0, 1], { easing: ease, extrapolateRight: 'clamp' });
  const s = z0[0] + (zEnd[0] - z0[0]) * t;
  const cx = z0[1] + (zEnd[1] - z0[1]) * t;
  const cy = z0[2] + (zEnd[2] - z0[2]) * t;
  const tx = 960 - cx * s;
  const ty = 540 - cy * s;
  return (
    <Fade dur={dur} inF={8} outF={8}>
      <AbsoluteFill style={{ background: C.kinari, overflow: 'hidden' }}>
        <div style={{ position: 'absolute', left: 0, top: 0, width: 1920, height: 1080, transformOrigin: '0 0', transform: `translate(${tx}px, ${ty}px) scale(${s})` }}>
          <OffthreadVideo src={staticFile(src)} muted trimBefore={Math.round(from * fps)} playbackRate={rate} style={{ width: 1920, height: 1080 }} />
        </div>
        {label && <div style={{ position: 'absolute', left: 36, top: 30, fontFamily: maru }}><Chip size={20} bg="rgba(42,38,34,.78)">● {label}</Chip></div>}
        {badge && <div style={{ position: 'absolute', right: 40, top: 30, fontFamily: maru }}><Chip size={22} bg={C.shu}>{badge}</Chip></div>}
      </AbsoluteFill>
    </Fade>
  );
};

// ---------------------------------------------------------------- 図(SVG)
export const SvgScene: React.FC<{ dur: number; src: string; title?: string; sub?: string; zoomTo?: number }> = ({ dur, src, title, sub, zoomTo = 1.03 }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sp = spring({ frame: f, fps, config: { damping: 18 } });
  const s = interpolate(f, [0, dur], [1, zoomTo]);
  return (
    <Fade dur={dur} inF={10} outF={10}>
      <Washi>
        {title && <div style={{ position: 'absolute', left: 110, top: 54, fontSize: 40, fontWeight: 900, color: C.sumi }}>{title}{sub && <span style={{ fontSize: 24, fontWeight: 500, color: C.sumi3, marginLeft: 20 }}>{sub}</span>}</div>}
        <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', paddingTop: title ? 70 : 0 }}>
          <Img src={staticFile(src)} style={{ width: 1720, transform: `scale(${(0.96 + sp * 0.04) * s})`, opacity: sp, borderRadius: 30 }} />
        </AbsoluteFill>
      </Washi>
    </Fade>
  );
};

// ---------------------------------------------------------------- Claude の使い方(バッジ)
export const ClaudeScene: React.FC<{ dur: number }> = ({ dur }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const groups: { head: string; color: string; items: string[] }[] = [
    { head: 'Claude API', color: C.ai, items: ['Haiku 5.5 · 構造化出力(聞き役)', 'Sonnet 5.5 · Citations(反証役)', 'Sonnet 5.5 · 記憶と照合(まとめ役)', 'Opus 5.5 · 今すぐの便り', 'プロンプトキャッシュ'] },
    { head: 'Claude Managed Agents', color: C.shu, items: ['Sonnet 5.5 の便り係(毎日)', '記憶ストア', 'スキル', '定期実行 18:00', 'Outcomes(採点役)', 'ant apply'] },
    { head: 'Claude Code(開発)', color: C.wakatake, items: ['フック: 原則の番人・自動評価', 'サブエージェント: 監査役・評価係', 'スキル', 'MCP: 通話カルテ'] },
  ];
  let k = 0;
  return (
    <Fade dur={dur}>
      <Washi>
        <div style={{ position: 'absolute', left: 120, top: 90, fontSize: 46, fontWeight: 900, color: C.sumi }}>役割ごとに、Claude を選ぶ</div>
        <div style={{ position: 'absolute', left: 120, right: 120, top: 210, display: 'flex', flexDirection: 'column', gap: 34 }}>
          {groups.map((g, gi) => (
            <div key={gi} style={{ display: 'flex', alignItems: 'flex-start', gap: 26 }}>
              <div style={{ minWidth: 380, fontSize: 30, fontWeight: 900, color: g.color, paddingTop: 10 }}>{g.head}</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14 }}>
                {g.items.map((it) => {
                  const sp = spring({ frame: f - 10 - (k++) * 4, fps, config: { damping: 14 } });
                  return <span key={it} style={{ opacity: sp, transform: `translateY(${(1 - sp) * 14}px)`, background: C.paper, border: `2px solid ${C.line}`, borderRadius: 18, padding: '12px 20px', fontSize: 26, color: C.sumi, fontWeight: 700, boxShadow: '0 6px 16px rgba(84,56,30,.08)' }}>{it}</span>;
                })}
              </div>
            </div>
          ))}
        </div>
      </Washi>
    </Fade>
  );
};

// ---------------------------------------------------------------- 終わり(実写の障子が開いて、ふすまの向こうへ)
export const EndingScene: React.FC<{ dur: number; bg: string; panel: string }> = ({ dur, bg, panel }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const open = interpolate(f, [24, 110], [0, 1], { easing: Easing.bezier(0.5, 0, 0.2, 1), extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const bgS = interpolate(f, [0, dur], [1.12, 1.02]);
  const txt = spring({ frame: f - 120, fps, config: { damping: 16 } });
  const logo = spring({ frame: f - 210, fps, config: { damping: 16 } });
  return (
    <Fade dur={dur} inF={10} outF={26}>
      <AbsoluteFill style={{ background: '#000', overflow: 'hidden' }}>
        <Img src={staticFile(bg)} style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${bgS})`, filter: 'saturate(0.95) brightness(0.92)' }} />
        <AbsoluteFill style={{ background: `rgba(30,20,12,${0.35 * txt})` }} />
        {[0, 1].map((side) => (
          <div key={side} style={{ position: 'absolute', top: 0, bottom: 0, width: 960, left: side === 0 ? -960 * open : 960 + 960 * open, overflow: 'hidden', borderLeft: side === 1 ? `14px solid ${C.wood}` : undefined, borderRight: side === 0 ? `14px solid ${C.wood}` : undefined, boxShadow: '0 0 60px rgba(0,0,0,.4)' }}>
            <Img src={staticFile(panel)} style={{ width: 1920, height: 1080, objectFit: 'cover', marginLeft: side === 0 ? 0 : -960, filter: 'sepia(0.35) brightness(1.05)' }} />
          </div>
        ))}
        <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', flexDirection: 'column', fontFamily: maru, color: '#fff', textShadow: '0 4px 24px rgba(0,0,0,.55)' }}>
          <div style={{ fontSize: 64, fontWeight: 700, letterSpacing: '0.14em', opacity: txt, transform: `translateY(${(1 - txt) * 20}px)` }}>離れていても、ふすま一枚向こうに。</div>
          <div style={{ fontSize: 120, fontWeight: 900, letterSpacing: '0.12em', marginTop: 40, opacity: logo }}>ふすまごし</div>
          <div style={{ fontSize: 26, marginTop: 22, opacity: logo * 0.9, letterSpacing: '0.1em' }}>Built with Claude · Claude Code · Claude Managed Agents</div>
        </AbsoluteFill>
      </AbsoluteFill>
    </Fade>
  );
};

// ---------------------------------------------------------------- 字幕
export const Captions: React.FC<{ items: { start: number; end: number; text: string; who?: string; size?: number }[] }> = ({ items }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = f / fps;
  const cur = items.filter((c) => t >= c.start && t < c.end);
  if (!cur.length) return null;
  const c = cur[cur.length - 1];
  const o = Math.min(interpolate(t, [c.start, c.start + 0.18], [0, 1], { extrapolateRight: 'clamp' }), interpolate(t, [c.end - 0.18, c.end], [1, 0], { extrapolateLeft: 'clamp' }));
  const who = c.who && c.who !== 'narr' ? ({ grandma: '祖母', fusuma: 'ふすまごし', kenta: '健太' } as Record<string, string>)[c.who] : null;
  const col = c.who === 'grandma' ? '#cfe7d9' : c.who === 'fusuma' ? '#ffe1a6' : c.who === 'kenta' ? '#cfdcf2' : '#fff';
  return (
    <AbsoluteFill style={{ justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 64, pointerEvents: 'none' }}>
      <div style={{ opacity: o, maxWidth: 1500, background: 'rgba(28,22,18,.66)', borderRadius: 22, padding: '16px 34px', fontFamily: c.who === 'grandma' ? klee : maru, fontSize: c.size ?? 44, lineHeight: 1.45, color: '#fff', textAlign: 'center', backdropFilter: 'blur(6px)', whiteSpace: 'pre-line', textWrap: 'balance' } as React.CSSProperties}>
        {who && <span style={{ fontFamily: maru, fontSize: 24, fontWeight: 700, color: col, marginRight: 16, verticalAlign: 'middle' }}>{who}</span>}
        {c.text}
      </div>
    </AbsoluteFill>
  );
};
