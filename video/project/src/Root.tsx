import { Composition } from 'remotion';
import { Fusumagoshi } from './Fusumagoshi';
import { FusumagoshiV2 } from './FusumagoshiV2';
import timeline from './data/timeline.json';
import timeline2 from './data/timeline_v2.json';

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="FusumagoshiV2" component={FusumagoshiV2} durationInFrames={Math.round((timeline2 as any).duration * 30)} fps={30} width={1920} height={1080} />
    <Composition id="Fusumagoshi" component={Fusumagoshi} durationInFrames={Math.round((timeline as any).duration * 30)} fps={30} width={1920} height={1080} />
  </>
);
