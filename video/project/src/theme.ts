import { loadFont as loadMaru } from '@remotion/google-fonts/ZenMaruGothic';
import { loadFont as loadKlee } from '@remotion/google-fonts/KleeOne';
import { loadFont as loadMincho } from '@remotion/google-fonts/ShipporiMinchoB1';
import { loadFont as loadGothic } from '@remotion/google-fonts/ZenKakuGothicNew';

export const maru = loadMaru('normal', { weights: ['400', '500', '700', '900'] }).fontFamily;
export const klee = loadKlee('normal', { weights: ['400', '600'] }).fontFamily;
export const mincho = loadMincho('normal', { weights: ['500', '800'] }).fontFamily;
export const gothic = loadGothic('normal', { weights: ['500'] }).fontFamily;

export const C = {
  kinari: '#f7f1e5',
  washi: '#fbf7ee',
  paper: '#fffdf8',
  sumi: '#2a2622',
  sumi2: '#5b524a',
  sumi3: '#8d837a',
  line: '#e7dccb',
  wood: '#8a5a3b',
  shu: '#e0573d',
  yamabuki: '#f2b13a',
  wakatake: '#5fa184',
  ai: '#2f4a6d',
  night: '#1f2230',
};

/** v2: 和紙・墨・朱・藍・行灯の橙だけ */
export const K = {
  washi: '#f3ead8',
  washi2: '#ebdfc8',
  sumi: '#24201c',
  sumi2: '#4a423a',
  sumi3: '#857a6e',
  shu: '#c4432c',
  ai: '#2c4a6b',
  aiLight: 'rgba(44,74,107,.16)',
  tou: '#e99a3c',
  touLight: 'rgba(233,154,60,.22)',
};
