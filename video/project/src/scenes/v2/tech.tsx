import React from 'react';
import { AbsoluteFill, Img, OffthreadVideo, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';
import { Appear, Fade, InkPath, K, Note, Paper, Postmark, Stamp, gothic, klee, mincho, ramp, useT } from './base';

const Title: React.FC<{ t0?: number; text: string; sub?: string }> = ({ t0 = 0, text, sub }) => (
  <Appear t0={t0} style={{ position: 'absolute', left: 110, top: 70 }}>
    <div style={{ fontSize: 58, fontWeight: 800, letterSpacing: '0.08em' }}>{text}</div>
    {sub && <div style={{ fontSize: 28, color: K.sumi3, marginTop: 8, fontFamily: gothic }}>{sub}</div>}
  </Appear>
);

const Tag: React.FC<{ t0: number; t1?: number; x: number; y: number; children: React.ReactNode; size?: number; color?: string; bold?: boolean }> = ({ t0, t1, x, y, children, size = 30, color = K.sumi, bold }) => (
  <Appear t0={t0} t1={t1} style={{ position: 'absolute', left: x, top: y, fontSize: size, color, fontWeight: bold ? 800 : 500, fontFamily: mincho, letterSpacing: '0.03em', lineHeight: 1.4 }}>{children}</Appear>
);

/* ---------------------------------------------------------------- s04 行灯の絵(台所の棚・マイク・Mac・電話回線にはつながない) */
export const AndonDiagram: React.FC<{ dur: number; T?: { lamp?: number; mic?: number; phone?: number; only?: number; off?: number } }> = ({ dur, T = {} }) => {
  const t = useT();
  const L = T.lamp ?? 1.9, M = T.mic ?? 3.0, P = T.phone ?? 4.6, O = T.only ?? 6.4, F = T.off ?? 7.6;
  const glow = interpolate(t, [L + 0.3, L + 1.1, F, F + 0.8], [0, 1, 1, 0.06], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const title = ramp(t, 0.05, 0.4) * (1 - ramp(t, L - 0.3, 0.4));
  return (
    <Fade dur={dur} inF={4}>
      <Paper>
        <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', opacity: title }}>
          <div style={{ fontSize: 170, fontWeight: 800, letterSpacing: '0.2em', color: K.sumi }}>ふすまごし</div>
        </AbsoluteFill>
        <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0 }}>
          {/* 棚 */}
          <InkPath d="M 300 640 L 760 640" t0={L} dur={0.4} width={6} />
          <InkPath d="M 330 640 L 330 700 M 730 640 L 730 700" t0={L + 0.1} dur={0.3} width={5} />
          {/* 行灯 */}
          <g>
            <rect x={460} y={380} width={150} height={250} rx={6} fill={`rgba(233,154,60,${0.55 * glow})`} stroke="none" />
            <InkPath d="M 450 372 L 620 372 M 450 636 L 620 636 M 462 372 L 462 636 M 608 372 L 608 636 M 535 372 L 535 636 M 462 460 L 608 460 M 462 548 L 608 548" t0={L + 0.1} dur={0.8} width={5} />
            <circle cx={535} cy={505} r={190} fill={`rgba(233,154,60,${0.18 * glow})`} />
          </g>
          {/* マイク → Mac */}
          <InkPath d="M 900 470 C 960 470, 980 470, 1040 470" t0={M + 0.3} dur={0.4} width={4} />
          <InkPath d="M 860 430 a 26 34 0 1 1 52 0 l 0 40 a 26 30 0 1 1 -52 0 z M 886 504 L 886 540 M 862 540 L 910 540" t0={M} dur={0.5} width={4} />
          <InkPath d="M 1060 400 L 1330 400 L 1330 560 L 1060 560 Z M 1150 600 L 1240 600 M 1195 560 L 1195 600" t0={M + 0.5} dur={0.6} width={5} />
          {/* 電話機と、つながない線 */}
          <InkPath d="M 1500 520 C 1500 470, 1560 450, 1620 450 C 1680 450, 1740 470, 1740 520 L 1740 600 L 1500 600 Z M 1540 450 L 1700 450" t0={P} dur={0.6} width={5} />
          <InkPath d="M 1500 560 C 1430 560, 1400 520, 1340 500" t0={P + 0.4} dur={0.4} width={3} dash="10 10" />
          <InkPath d="M 1390 470 L 1440 530 M 1440 470 L 1390 530" t0={P + 0.8} dur={0.25} width={9} color={K.shu} />
        </svg>
        <Tag t0={M} x={820} y={600} size={28} color={K.sumi2}>部屋のマイク</Tag>
        <Tag t0={M + 0.6} x={1090} y={440} size={34} bold>Mac 1 台</Tag>
        <Tag t0={M + 0.7} x={1072} y={492} size={24} color={K.sumi2}>(音声は外に出さない)</Tag>
        <Tag t0={L + 0.4} x={410} y={720} size={26} color={K.sumi3}>台所の小さな行灯(イメージ)</Tag>
        <Tag t0={P + 0.9} x={1330} y={650} size={34} color={K.shu} bold>電話回線にはつながない</Tag>
        <Tag t0={O} x={760} y={800} size={46} bold>聞くのは、祖母の声だけ</Tag>
        <Tag t0={F + 0.7} x={700} y={880} size={46} bold color={K.ai}>通話中は、光らない・話さない</Tag>
        <Tag t0={F + 1.3} x={1010} y={970} size={25} color={K.sumi2}>Fusuma.say() → 通話中は SilenceViolation で止まる(実際のコード)</Tag>
      </Paper>
    </Fade>
  );
};

/* ---------------------------------------------------------------- s06 ふすまの裏側(間の図・比べる・Mac の中の流れ) */
type Seg = [number, number];
const Strip: React.FC<{ segs: Seg[]; total: number; x: number; y: number; w: number; h: number; t0: number; color: string; gap?: boolean; label: string; sub?: string }> = ({ segs, total, x, y, w, h, t0, color, gap, label, sub }) => {
  const t = useT();
  const sc = (s: number) => x + (s / total) * w;
  return (
    <g>
      <text x={x - 24} y={y + h * 0.66} textAnchor="end" fontFamily={mincho} fontSize={30} fontWeight={800} fill={K.sumi}>{label}</text>
      {sub && <text x={x - 24} y={y + h * 0.66 + 34} textAnchor="end" fontFamily={gothic} fontSize={22} fill={K.sumi3}>{sub}</text>}
      <rect x={x} y={y} width={w} height={h} fill="none" stroke={K.sumi3} strokeWidth={2} strokeDasharray={gap ? '8 8' : undefined} opacity={0.6} />
      {segs.map(([a, b], i) => {
        const p = ramp(t, t0 + (a / total) * 1.2, 0.2);
        return <rect key={i} x={sc(a)} y={y + 4} width={Math.max(4, (sc(b) - sc(a)) * p)} height={h - 8} fill={color} rx={3} />;
      })}
    </g>
  );
};

export const UraDiagram: React.FC<{ dur: number; s05: Seg[]; s05Total: number; s11: Seg[]; s11Total: number; line: string; postTime?: string; m: { gMax: number; fMax: number; gSelf: number; fSelf: number; gOther: number; fOther: number; dB: number } }> = ({ dur, s05, s05Total, s11, s11Total, line, postTime = '14:02', m }) => {
  const t = useT();
  const inv: Seg[] = [];
  let prev = 0;
  for (const [a, b] of s05) { if (a - prev > 1.2) inv.push([prev, a]); prev = b; }
  const phaseA = 1 - ramp(t, 2.0, 0.35);
  const phaseB = ramp(t, 2.1, 0.35) * (1 - ramp(t, 7.4, 0.35));
  const phaseC = ramp(t, 7.5, 0.35);
  const gate = ramp(t, 9.6, 0.5);
  return (
    <Fade dur={dur} inF={6}>
      <Paper>
        <Title text="ふすまの裏側" sub="早送りで" />
        {/* A: 聞こえる帯と、聞こえない帯 */}
        <AbsoluteFill style={{ opacity: phaseA }}>
          <svg width={1920} height={1080}>
            <Strip segs={s05} total={s05Total} x={380} y={360} w={1400} h={90} t0={0.2} color={K.tou} label="祖母" sub="(聞こえる)" />
            <Strip segs={inv.map(([a, b]) => [a, ramp(t, 0.9, 0.6) * (b - a) + a] as Seg)} total={s05Total} x={380} y={560} w={1400} h={90} t0={0.9} color={K.ai} gap label="相手" sub="(聞こえない)" />
          </svg>
          <div style={{ position: 'absolute', left: 1540, top: 700 }}><Stamp t0={1.4} text="推定" size={44} /></div>
        </AbsoluteFill>
        {/* B: 友だちとの電話 / この電話 */}
        <AbsoluteFill style={{ opacity: phaseB }}>
          <svg width={1920} height={1080}>
            <Strip segs={s11} total={s11Total} x={460} y={300} w={1300 * s11Total / Math.max(s05Total, s11Total)} h={80} t0={2.2} color={K.tou} label="友だちとの電話" sub={`${Math.round(s11Total)} 秒`} />
            <Strip segs={s05} total={s05Total} x={460} y={470} w={1300 * s05Total / Math.max(s05Total, s11Total)} h={80} t0={2.5} color={K.tou} label="この電話" sub={`${Math.floor(s05Total / 60)} 分 ${Math.round(s05Total % 60)} 秒`} />
            {[0, 30, 60, 90].map((sec) => {
              const x = 460 + sec * (1300 / Math.max(s05Total, s11Total));
              return <g key={sec} opacity={ramp(t, 2.6, 0.3)}><line x1={x} y1={556} x2={x} y2={568} stroke={K.sumi3} strokeWidth={2} /><text x={x} y={590} textAnchor="middle" fontFamily={gothic} fontSize={20} fill={K.sumi3}>{sec} 秒</text></g>;
            })}
            {[{ segs: s11, total: s11Total, y: 300, label: `${m.fMax}秒` }, { segs: s05, total: s05Total, y: 470, label: `${m.gMax}秒` }].map((b, k) => {
              const pps = 1300 / Math.max(s05Total, s11Total);
              let best: Seg = [0, 0];
              for (let i = 1; i < b.segs.length; i++) { const g: Seg = [b.segs[i - 1][1], b.segs[i][0]]; if (g[1] - g[0] > best[1] - best[0]) best = g; }
              const xa = 460 + best[0] * pps, xb = 460 + best[1] * pps, op = ramp(t, 2.9, 0.3);
              return <g key={k} opacity={op}><path d={`M ${xa} ${b.y - 6} V ${b.y - 20} H ${xb} V ${b.y - 6}`} fill="none" stroke={K.shu} strokeWidth={3} /><text x={(xa + xb) / 2} y={b.y - 28} textAnchor="middle" fontFamily={mincho} fontSize={28} fontWeight={800} fill={K.shu}>{b.label}</text></g>;
            })}
          </svg>
          {[
            [2.9, `最長の沈黙 ${m.fMax}秒 → ${m.gMax}秒`],
            [3.8, `祖母 ${m.fSelf}% → ${m.gSelf}% / 相手(推定) ${m.fOther}% → ${m.gOther}%`],
            [4.8, '断りの言葉 前半1 → 後半0'],
            [5.6, `「じゃあ、お願いします」声量 ${m.dB}dB`],
          ].map(([t0, s], i) => (
            <div key={i} style={{ position: 'absolute', left: 460 + (i % 2) * 660, top: 620 + Math.floor(i / 2) * 110 }}><Stamp t0={t0 as number} text={s as string} size={34} rot={i % 2 ? 2 : -3} color={i === 0 ? K.shu : K.sumi} /></div>
          ))}
          <Tag t0={6.4} x={460} y={880} size={28} color={K.sumi2}>0.6 秒未満の「はい」は、あいづち(同意に数えない)</Tag>
        </AbsoluteFill>
        {/* C: Mac の中で 4 つの箱が順に灯り、関所を通るのは文字の 1 行だけ */}
        <AbsoluteFill style={{ opacity: phaseC }}>
          <svg width={1920} height={1080}>
            <rect x={120} y={250} width={1300} height={560} rx={26} fill="rgba(255,255,255,.35)" stroke={K.sumi} strokeWidth={4} />
            <text x={150} y={300} fontFamily={mincho} fontSize={30} fontWeight={800} fill={K.sumi}>Mac の中</text>
            <rect x={1420} y={250} width={14} height={560} fill={K.shu} opacity={0.85} />
          </svg>
          {[
            ['呼出音・受話器', 'YAMNet(ONNX)'],
            ['声の区間', 'Silero VAD'],
            ['文字起こし', 'whisper.cpp large-v3-turbo(Metal)'],
            ['声の高さ・\n大きさ・速さ', 'Praat(いつもの声との差)'],
          ].map(([a, b], i) => {
            const on = ramp(t, 7.7 + i * 0.45, 0.25);
            return (
              <div key={i} style={{ position: 'absolute', left: 170 + i * 310, top: 360, width: 280, height: 190, borderRadius: 16, border: `3px solid ${K.sumi}`, background: `rgba(233,154,60,${0.08 + 0.32 * on})`, padding: '18px 16px', boxSizing: 'border-box', fontFamily: mincho }}>
                <div style={{ fontSize: 30, fontWeight: 800, lineHeight: 1.3, whiteSpace: 'pre-line' }}>{a}</div>
                <div style={{ fontSize: 22, marginTop: 12, fontFamily: gothic, color: K.sumi2, lineHeight: 1.35 }}>{b}</div>
              </div>
            );
          })}
          <div style={{ position: 'absolute', left: 170, top: 610, width: 1220, padding: '18px 22px', borderRadius: 12, background: K.sumi, color: '#f3ead8', fontFamily: gothic, fontSize: 27, opacity: ramp(t, 9.5, 0.3), letterSpacing: '0.01em' }}>{line}</div>
          <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0 }}>
            <path d={`M 170 760 ${Array.from({ length: 40 }, (_, i) => `L ${170 + i * 31} ${760 + Math.sin(i * 1.7) * 22 * (1 - gate * (i > 30 ? 1 : 0))}`).join(' ')}`} fill="none" stroke={K.ai} strokeWidth={3} opacity={0.8} />
          </svg>
          <Tag t0={9.9} x={1460} y={600} size={34} bold>Claude へは、</Tag>
          <Tag t0={9.9} x={1460} y={648} size={34} bold>文字と数値だけ</Tag>
          <Tag t0={10.5} x={1460} y={740} size={40} bold color={K.shu}>音声 0 バイト</Tag>
          <Tag t0={11.0} x={1460} y={800} size={22} color={K.sumi3}>送った量と時刻は、台帳に残る</Tag>
          <Postmark t0={11.0} time={postTime} label="耳" x={1610} y={300} />
        </AbsoluteFill>
      </Paper>
    </Fade>
  );
};

/* ---------------------------------------------------------------- s07 ふすまの向こうの家族会議(ちゃぶ台と三つの座布団) */
export const KaigiDiagram: React.FC<{ dur: number; score: number; genuine: string; restraint: string; cite?: string; postTime?: string }> = ({ dur, score, genuine, restraint, cite = '電話注文で意図せず定期購入に', postTime = '14:04' }) => {
  const t = useT();
  const stages = ['案内', '強い勧め', '申込の約束', '支払い・定期購入の約束'];
  const needle = interpolate(t, [0.4, 2.6], [0, 3], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const part = ramp(t, 2.9, 0.4);
  const lamps = ramp(t, 7.6, 0.3);
  const cushion = (x: number, y: number, ch: string, on: number) => (
    <div style={{ position: 'absolute', left: x, top: y, width: 150, height: 150, borderRadius: 26, background: on ? '#e9c9a6' : '#e6d8c2', border: `3px solid ${K.sumi}`, boxShadow: on ? `0 0 0 10px rgba(233,154,60,${0.3 * on})` : 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: mincho, fontSize: 64, fontWeight: 800, color: K.sumi }}>{ch}</div>
  );
  return (
    <Fade dur={dur} inF={6}>
      <Paper>
        <Title text="ふすまの向こうの家族会議" sub="3 つの Claude が、順に判断をつなぐ" />
        <div style={{ position: 'absolute', left: 760, top: 400, width: 400, height: 260, borderRadius: 40, background: '#c7a27a', border: `4px solid ${K.sumi}`, opacity: 0.9 }} />
        {cushion(560, 455, '聞', ramp(t, 0.2, 0.3) * (1 - ramp(t, 2.9, 0.3)))}
        {cushion(880, 220, '反', ramp(t, 2.9, 0.3) * (1 - ramp(t, 7.5, 0.3)))}
        {cushion(1210, 455, 'ま', ramp(t, 7.5, 0.3))}
        {/* 聞き役: 段階のものさし */}
        <div style={{ position: 'absolute', left: 120, top: 720, width: 760, opacity: (1 - ramp(t, 2.8, 0.3) * 0.65) * (1 - ramp(t, 7.4, 0.3)) }}>
          <div style={{ fontFamily: mincho, fontSize: 28, fontWeight: 800 }}>聞き役 Claude Haiku 5.5<span style={{ fontFamily: gothic, fontSize: 22, color: K.sumi3, marginLeft: 12 }}>構造化出力・10 発話か 60 秒ごと</span></div>
          <div style={{ position: 'relative', marginTop: 18, height: 56, borderTop: `3px solid ${K.sumi}` }}>
            {stages.map((s, i) => <div key={i} style={{ position: 'absolute', left: `${i * 31}%`, top: 10, fontFamily: mincho, fontSize: 24, color: i <= needle + 0.01 ? K.sumi : K.sumi3, fontWeight: i <= needle + 0.01 ? 800 : 500, whiteSpace: 'nowrap' }}>{s}</div>)}
            <div style={{ position: 'absolute', left: `${needle * 31}%`, top: -22, width: 0, height: 0, borderLeft: '12px solid transparent', borderRight: '12px solid transparent', borderTop: `18px solid ${K.shu}` }} />
          </div>
          <div style={{ marginTop: 14 }}><Stamp t0={2.2} text={`怪しい度 ${score.toFixed(2)}(通話後の最終判定)`} size={28} /></div>
        </div>
        {/* 反証役: 仕切りが閉まる・カードが開く */}
        <div style={{ position: 'absolute', left: 735, top: 190, width: 16, height: 300 * part, background: K.sumi, borderRadius: 4 }} />
        <Tag t0={3.2} t1={7.5} x={1060} y={230} size={28} bold>反証役 Claude Sonnet 5.5</Tag>
        <Tag t0={3.4} t1={7.5} x={1060} y={274} size={26} color={K.shu} bold>聞き役の結論は渡さない(独立した文脈)</Tag>
        <AbsoluteFill style={{ opacity: ramp(t, 3.9, 0.3) * (1 - ramp(t, 7.4, 0.3)) }}>
          {['消費者庁', '警察庁', '国民生活センター', '全国銀行協会'].map((s, i) => (
            <div key={i} style={{ position: 'absolute', left: 1080 + i * 150, top: 340, width: 190, height: 250, background: '#fffaf0', border: `2px solid ${K.sumi2}`, borderRadius: 10, transform: `rotate(${(i - 1.5) * 7 * ramp(t, 4.0, 0.5)}deg)`, transformOrigin: 'bottom center', boxShadow: '0 8px 18px rgba(60,40,20,.15)', padding: 14, boxSizing: 'border-box', fontFamily: mincho, fontSize: 22, fontWeight: 800 }}>{s}</div>
          ))}
          <Tag t0={4.4} x={1080} y={620} size={24} color={K.sumi2}>知識カード 21 枚 → search_result + Citations で出典つき</Tag>
          <Note t0={5.2} x={1080} y={680} w={720} size={26}>出典「<span style={{ textDecoration: `underline ${K.shu} 3px`, textUnderlineOffset: 6 }}>{cite}</span>」</Note>
          <div style={{ position: 'absolute', left: 1500, top: 820 }}><Stamp t0={6.2} text={`本物の可能性: ${genuine}`} size={30} rot={3} /></div>
        </AbsoluteFill>
        {/* まとめ役: 三つの行灯 */}
        <AbsoluteFill style={{ opacity: lamps }}>
          {['黙る', '夕方の便り', '今すぐ家族へ'].map((s, i) => {
            const lit = i === 1 ? ramp(t, 8.6, 0.5) : 0;
            return (
              <div key={i} style={{ position: 'absolute', left: 1080 + i * 240, top: 200, width: 190, textAlign: 'center', fontFamily: mincho }}>
                <div style={{ width: 90, height: 140, margin: '0 auto', border: `4px solid ${K.sumi}`, background: `rgba(233,154,60,${0.08 + 0.75 * lit})`, boxShadow: lit ? `0 0 60px rgba(233,154,60,${0.6 * lit})` : 'none' }} />
                <div style={{ fontSize: 28, fontWeight: 800, marginTop: 12, color: lit ? K.sumi : K.sumi3 }}>{s}</div>
              </div>
            );
          })}
          <Tag t0={7.6} x={1080} y={150} size={28} bold>まとめ役 Claude Sonnet 5.5</Tag>
          <Note t0={9.1} x={1060} y={640} w={780} size={25}>抑えた理由「{restraint}」</Note>
          <Tag t0={9.8} x={120} y={760} size={24} color={K.sumi2}>今すぐ家族へ = 今日お金・カードが動く / 知らない人が来る / 口止め のときだけ</Tag>
          <Postmark t0={10.6} time={postTime} label="聞き役・反証役・まとめ役" x={140} y={250} />
        </AbsoluteFill>
      </Paper>
    </Fade>
  );
};

/* ---------------------------------------------------------------- s09 文字起こしが消える(「つい」だけが残る) */
export const TsuiScene: React.FC<{ dur: number; lines: string[]; fromClock?: string; video?: string; from?: number }> = ({ dur, lines, fromClock = '14:05', video, from = 0 }) => {
  const t = useT();
  const dissolve = ramp(t, 0.5, 1.6);
  const light = interpolate(t, [0, dur / 30], [0, 1], { extrapolateRight: 'clamp' });
  return (
    <Fade dur={dur} inF={6}>
      <AbsoluteFill style={{ background: '#000' }}>
        {video
          ? <OffthreadVideo src={staticFile(video)} startFrom={Math.round(from * 30)} muted style={{ width: '100%', height: '100%', objectFit: 'cover', filter: `sepia(${0.15 + 0.35 * light}) saturate(${1 - 0.15 * light}) brightness(${0.95 - 0.3 * light})`, transform: `scale(1.04)` }} />
          : <Img src={staticFile('img/shoji_windowlight.jpg')} style={{ width: '100%', height: '100%', objectFit: 'cover', filter: `sepia(${0.1 + 0.3 * light}) brightness(${1 - 0.25 * light})`, transform: `scale(1.06) translateX(${-30 * light}px)` }} />}
        <AbsoluteFill style={{ background: `linear-gradient(${100 + 40 * light}deg, rgba(255,214,150,.0) 30%, rgba(255,190,110,${0.18 + 0.2 * light}) 60%, rgba(0,0,0,.25) 100%)` }} />
        <div style={{ position: 'absolute', left: 240, top: 210, width: 1440, fontFamily: mincho, fontSize: 40, lineHeight: 1.9, color: K.sumi }}>
          {lines.map((l, i) => {
            const parts = l.split('つい');
            const fade = { opacity: 1 - dissolve * (0.8 + i * 0.04), filter: `blur(${dissolve * 6}px)` };
            return <div key={i}><span style={fade}>{parts[0]}</span>{parts.length > 1 && <span style={{ color: K.shu, fontWeight: 800, display: 'inline-block', transform: `scale(${1 + 0.35 * dissolve})`, transformOrigin: 'center bottom', textShadow: `0 0 ${18 * dissolve}px rgba(255,240,220,.9)` }}>つい</span>}<span style={fade}>{parts.slice(1).join('つい')}</span></div>;
          })}
        </div>
        <div style={{ position: 'absolute', left: 0, right: 0, top: 640, textAlign: 'center', opacity: ramp(t, 1.8, 0.5), fontFamily: mincho, fontSize: 36, color: '#fbf4e6', textShadow: '0 2px 18px rgba(0,0,0,.6)' }}>会話が終わると、文字起こしは消える(残るのは短いカルテだけ)</div>
        <div style={{ position: 'absolute', right: 80, top: 60, fontFamily: mincho, fontSize: 44, fontWeight: 800, color: '#fbf4e6', textShadow: '0 2px 18px rgba(0,0,0,.6)' }}>{t < dur / 30 * 0.55 ? fromClock : '→ 18:00'}</div>
      </AbsoluteFill>
    </Fade>
  );
};

/* ---------------------------------------------------------------- s10 夕方の便りのできるまで(左に流れ図、採点役の実際の文) */
export const LetterFlow: React.FC<{ dur: number; t0?: number; evals?: { ok: boolean; text: string }[]; tool?: string }> = ({ dur, t0 = 0, evals = [], tool = 'read /mnt/memory/fusuma-memory/karte/…' }) => {
  const t = useT() - t0;
  const steps = ['18:00 定期実行', '記憶ストア(カルテ・暮らしのメモ・家族の文脈)', 'スキル fusuma-letter が書く', '採点役 Outcomes(別の文脈)', '合格した便りだけが届く(採点は最大 3 回)'];
  const last = evals[evals.length - 1];
  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      <div style={{ position: 'absolute', left: 60, top: 110, width: 780, padding: '30px 34px', background: 'rgba(243,234,216,.97)', borderRadius: 18, boxShadow: '0 20px 40px rgba(40,25,10,.25)', opacity: ramp(t, 0, 0.3), fontFamily: mincho }}>
        <div style={{ fontSize: 30, fontWeight: 800, marginBottom: 14 }}>毎日 18:00 Claude Managed Agents</div>
        {steps.map((s, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 14, opacity: ramp(t, 0.2 + i * 0.45, 0.25), margin: '10px 0' }}>
            <div style={{ width: 40, height: 40, borderRadius: '50%', border: `3px solid ${K.sumi}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: 22 }}>{i + 1}</div>
            <div style={{ fontSize: 26, fontWeight: i === 3 ? 800 : 500, color: i === 3 ? K.shu : K.sumi }}>{s}</div>
          </div>
        ))}
        <div style={{ marginTop: 16, fontFamily: gothic, fontSize: 19, color: K.sumi3, opacity: ramp(t, 2.4, 0.3), wordBreak: 'break-all', lineHeight: 1.4 }}>{tool}(実録のツール呼び出し)</div>
        {evals.map((e, i) => (
          <div key={i} style={{ marginTop: i ? 10 : 18, padding: '12px 18px', borderLeft: `6px solid ${e.ok ? K.shu : K.sumi3}`, fontSize: 24, lineHeight: 1.5, opacity: ramp(t, 2.9 + i * 0.9, 0.3) }}>{e.ok ? '✓' : '✕'} {i + 1} 回目「{e.text}」</div>
        ))}
        <div style={{ marginTop: 16, display: 'flex', gap: 24, alignItems: 'center' }}>{last?.ok && <Stamp t0={t0 + 3.2 + evals.length * 0.9} text={evals.length > 1 ? `書き直し ${evals.length - 1} 回 → 合格` : '採点 合格'} size={34} />}<span style={{ fontSize: 19, color: K.sumi3, fontFamily: gothic, opacity: ramp(t, 4.2, 0.3) }}>収録では同じ配備を手動で起動</span></div>
      </div>
    </AbsoluteFill>
  );
};

/* ---------------------------------------------------------------- s11 試験の結果と、Claude Code での作り方 */
export const ProofScene: React.FC<{ dur: number; hook: string }> = ({ dur, hook }) => {
  const t = useT();
  const bar = (x: number, y: number, val: number, max: number, color: string, label: string, t0: number) => {
    const p = ramp(t, t0, 0.6);
    return (
      <div style={{ position: 'absolute', left: x, top: y - 34 }}>
        <div style={{ fontFamily: mincho, fontSize: 30, fontWeight: 800, marginBottom: 6 }}>{label}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}><div style={{ width: 1000 * (val / max) * p + 6, height: 46, background: color, borderRadius: 4 }} />{val === 0 && <span style={{ fontFamily: mincho, fontSize: 44, fontWeight: 800, color }}>0</span>}</div>
      </div>
    );
  };
  const partA = 1 - ramp(t, 6.8, 0.35);
  const partB = ramp(t, 7.0, 0.35);
  return (
    <Fade dur={dur} inF={6}>
      <Paper>
        <AbsoluteFill style={{ opacity: partA }}>
          <Title text="架空の 15 通話 × 4 回" sub="台本は作者が作成。統計的な主張はしない" />
          <Tag t0={0.3} x={110} y={250} size={30} bold>本物の電話(警察署・信用金庫・医院・宅配・友人)に口を出した</Tag>
          {bar(110, 310, 0, 20, K.shu, 'ふすまごし 0 / 20', 0.6)}
          {bar(110, 410, 8, 20, K.sumi3, 'キーワード検知 8 / 20', 0.9)}
          <Tag t0={1.8} x={110} y={540} size={30} bold>危ない電話(詐欺 4・勧誘 4)を見逃した</Tag>
          {bar(110, 600, 0, 32, K.shu, 'ふすまごし 0 / 32', 2.1)}
          {bar(110, 700, 12, 32, K.sumi3, 'キーワード検知 12 / 32', 2.4)}
          <div style={{ position: 'absolute', left: 1340, top: 360 }}><Stamp t0={3.4} text="動き 60 / 60" size={54} rot={-6} /></div>
          <Tag t0={3.8} x={1340} y={500} size={26} color={K.sumi2}>黙る / 夕方の便り / 今すぐ家族へ</Tag>
          <Tag t0={4.4} x={1340} y={590} size={34} bold color={K.ai}>評価 1 回(15 通話)約 $0.38</Tag>
          <Tag t0={4.6} x={1340} y={644} size={24} color={K.sumi2}>原則と知識カードはプロンプトキャッシュ。なしだと 約 $0.86</Tag>
        </AbsoluteFill>
        <AbsoluteFill style={{ opacity: partB }}>
          <Title t0={7.0} text="作ったのは、Claude Code と" />
          <div style={{ position: 'absolute', left: 110, top: 240, width: 1060, padding: '26px 30px', borderRadius: 14, background: '#fffaf0', border: `3px solid ${K.sumi}`, fontFamily: gothic, fontSize: 25, lineHeight: 1.6, opacity: ramp(t, 7.2, 0.3) }}>
            <div style={{ color: K.sumi3 }}>PreToolUse フック</div>
            <div style={{ color: K.shu, fontWeight: 500 }}>{hook}</div>
          </div>
          <div style={{ position: 'absolute', left: 110, top: 520, width: 520, padding: '22px 28px', borderRadius: 14, background: '#fffaf0', border: `3px solid ${K.sumi}`, fontFamily: gothic, fontSize: 28, opacity: ramp(t, 8.6, 0.3) }}>原則のテスト <b>29 passed</b><div style={{ fontSize: 20, color: K.sumi3 }}>API を使わずに、数十秒</div></div>
          <div style={{ position: 'absolute', left: 680, top: 520, width: 1120, padding: '22px 28px', borderRadius: 14, background: '#fffaf0', border: `3px solid ${K.sumi}`, fontFamily: mincho, fontSize: 28, opacity: ramp(t, 10.0, 0.3) }}>最終レビュー: 6 観点 → 別のエージェントが 1 件ずつ反証 → 確かめた <b>80 件</b>を修正</div>
          {['サブエージェント 4(監査役・評価係・シナリオ作者・知識カード作者)', 'MCP サーバー(通話カルテを読み取り専用で)', 'スキル(原則・シナリオ合成)'].map((s, i) => (
            <Tag key={i} t0={11.2 + i * 0.5} x={680} y={680 + i * 56} size={26} color={K.sumi2}>・{s}</Tag>
          ))}
        </AbsoluteFill>
      </Paper>
    </Fade>
  );
};
