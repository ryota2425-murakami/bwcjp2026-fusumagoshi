import React from 'react';
import { AbsoluteFill, Audio, Sequence, interpolate, staticFile, useVideoConfig } from 'remotion';
import timeline from './data/timeline_v2.json';
import { Black, PhotoKB, VideoKB } from './scenes/v2/story';
import { AndonDiagram, KaigiDiagram, ProofScene, TsuiScene, UraDiagram } from './scenes/v2/tech';
import { Captions2, EndScene, FusumaSlide, Ghost, RecScene } from './scenes/v2/rec';
import { Warp } from './scenes/v2/base';
import { CharOverlay } from './scenes/v2/char';

type Scene = { kind: string; start: number; dur: number; layer?: number; [k: string]: any };
type Clip = { src: string; start: number; from?: number; dur?: number; volume?: number; fadeIn?: number; fadeOut?: number; rate?: number };

const SceneView: React.FC<{ s: Scene; durF: number }> = ({ s, durF }) => {
  const p: any = { ...s, dur: durF };
  switch (s.kind) {
    case 'photo': return <PhotoKB {...p} />;
    case 'video': return <VideoKB {...p} />;
    case 'black': return <Black dur={durF} />;
    case 'andon': return <AndonDiagram dur={durF} />;
    case 'ura': return <UraDiagram {...p} />;
    case 'kaigi': return <KaigiDiagram {...p} />;
    case 'tsui': return <TsuiScene {...p} />;
    case 'proof': return <ProofScene {...p} />;
    case 'rec': return <RecScene {...p} />;
    case 'end': return <EndScene {...p} />;
    case 'ghost': return <Ghost {...p} />;
    case 'slide': return <FusumaSlide {...p} />;
    case 'char': return <CharOverlay {...p} />;
    default: return null;
  }
};

const ClipAudio: React.FC<{ c: Clip; fps: number }> = ({ c, fps }) => {
  const durF = Math.max(1, Math.round((c.dur ?? 60) * fps));
  const fi = (c.fadeIn ?? 0) * fps;
  const fo = (c.fadeOut ?? 0) * fps;
  const v = c.volume ?? 1;
  return (
    <Sequence from={Math.round(c.start * fps)} durationInFrames={durF} layout="none">
      <Audio src={staticFile(c.src)} trimBefore={Math.round((c.from ?? 0) * fps)} playbackRate={c.rate ?? 1}
        volume={(f) => v * Math.min(fi ? interpolate(f, [0, fi], [0, 1], { extrapolateRight: 'clamp' }) : 1,
          fo ? interpolate(f, [durF - fo, durF], [1, 0], { extrapolateLeft: 'clamp' }) : 1)} />
    </Sequence>
  );
};

export const FusumagoshiV2: React.FC = () => {
  const { fps } = useVideoConfig();
  const tl = timeline as any;
  const scenes = (tl.scenes as Scene[]).slice().sort((a, b) => (a.layer ?? 0) - (b.layer ?? 0));
  return (
    <AbsoluteFill style={{ background: '#000' }}>
      {scenes.map((s, i) => {
        // 切り替えで黒く沈まないように: 下の層の場面は、次の場面が上でふわっと出きるまで残す(20 フレーム)
        const ext = (s.layer ?? 0) === 0 && s.kind !== 'end' ? 20 : 0;
        const durF = Math.max(1, Math.round(s.dur * fps)) + ext;
        return (
          <Sequence key={i} from={Math.round(s.start * fps)} durationInFrames={durF}>
            <Warp map={s.warp}><SceneView s={s} durF={durF} /></Warp>
          </Sequence>
        );
      })}
      <Captions2 items={tl.captions} />
      {(tl.audio as Clip[]).map((c, i) => <ClipAudio key={`a${i}`} c={c} fps={fps} />)}
    </AbsoluteFill>
  );
};
