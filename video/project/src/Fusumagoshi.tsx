import React from 'react';
import { AbsoluteFill, Audio, Sequence, interpolate, staticFile, useVideoConfig } from 'remotion';
import timeline from './data/timeline.json';
import { Captions, ClaudeScene, EndingScene, PhotoScene, ScreenScene, StatsScene, SvgScene, TitleScene, VideoScene } from './scenes/Scenes';

type Scene = { kind: string; start: number; dur: number; [k: string]: any };
type Clip = { src: string; start: number; from?: number; dur?: number; volume?: number; fadeIn?: number; fadeOut?: number };

const SceneView: React.FC<{ s: Scene; durF: number }> = ({ s, durF }) => {
  const p = { ...s, dur: durF };
  switch (s.kind) {
    case 'photo': return <PhotoScene {...(p as any)} />;
    case 'video': return <VideoScene {...(p as any)} />;
    case 'stats': return <StatsScene {...(p as any)} />;
    case 'title': return <TitleScene dur={durF} />;
    case 'screen': return <ScreenScene {...(p as any)} />;
    case 'svg': return <SvgScene {...(p as any)} />;
    case 'claude': return <ClaudeScene dur={durF} />;
    case 'ending': return <EndingScene {...(p as any)} />;
    default: return null;
  }
};

const ClipAudio: React.FC<{ c: Clip; fps: number }> = ({ c, fps }) => {
  const durF = Math.round((c.dur ?? 60) * fps);
  const fi = (c.fadeIn ?? 0) * fps;
  const fo = (c.fadeOut ?? 0) * fps;
  const v = c.volume ?? 1;
  return (
    <Sequence from={Math.round(c.start * fps)} durationInFrames={durF} layout="none">
      <Audio src={staticFile(c.src)} trimBefore={Math.round((c.from ?? 0) * fps)}
        volume={(f) => v * Math.min(fi ? interpolate(f, [0, fi], [0, 1], { extrapolateRight: 'clamp' }) : 1,
          fo ? interpolate(f, [durF - fo, durF], [1, 0], { extrapolateLeft: 'clamp' }) : 1)} />
    </Sequence>
  );
};

export const Fusumagoshi: React.FC = () => {
  const { fps } = useVideoConfig();
  const tl = timeline as any;
  return (
    <AbsoluteFill style={{ background: '#000' }}>
      {(tl.scenes as Scene[]).map((s, i) => (
        <Sequence key={i} from={Math.round(s.start * fps)} durationInFrames={Math.round(s.dur * fps)}>
          <SceneView s={s} durF={Math.round(s.dur * fps)} />
        </Sequence>
      ))}
      <Captions items={tl.captions} />
      {(tl.audio as Clip[]).map((c, i) => <ClipAudio key={`a${i}`} c={c} fps={fps} />)}
      {(tl.music as Clip[]).map((c, i) => <ClipAudio key={`m${i}`} c={c} fps={fps} />)}
    </AbsoluteFill>
  );
};
