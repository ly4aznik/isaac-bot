import {Video} from '@remotion/media';
import {AbsoluteFill, Composition, Easing, interpolate, Sequence, staticFile, useCurrentFrame} from 'remotion';

const FPS = 30;
const scenes = [
  {from: 0, duration: 8, kicker: 'THE GOAL', title: 'Teach an AI to beat\nThe Binding of Isaac', caption: 'I am building a bot that can explore floors, fight enemies, choose items, and defeat the final boss — without human input.', kind: 'game'},
  {from: 8, duration: 9, kicker: 'INPUT', title: 'The game state\nbecomes data', caption: 'The game state is read and sent to the AI: player position, walls, doors, enemies, pickups, and incoming projectiles.', kind: 'split'},
  {from: 17, duration: 8, kicker: 'CONTROL LOOP', title: 'Observe → Decide → Act', caption: 'The AI reads the situation, chooses an action, sends it back to the game, and checks the result — many times per second.', kind: 'game'},
  {from: 25, duration: 8, kicker: 'AUTOMATION', title: 'From launch\nto a live run', caption: 'The system can already launch the game, navigate the menus, start a normal run, and control movement and actions.', kind: 'game'},
  {from: 33, duration: 9, kicker: 'WORLD MODEL', title: 'This is what\nthe bot sees', caption: 'This schematic is the bot’s internal world model: walkable cells, obstacles, doors, entities, velocity, and the current goal.', kind: 'model'},
  {from: 42, duration: 10, kicker: 'PATHFINDING', title: 'Collision Grid → A*\n→ Waypoints', caption: 'The room becomes a collision grid. A-star finds a route around walls, rocks, and pits, while a controller follows the waypoints.', kind: 'split'},
  {from: 52, duration: 7, kicker: 'RECOVERY', title: 'Stuck?\nPlan again.', caption: 'If Isaac stops moving or drifts away from the route, replanning builds a new path from the current position.', kind: 'model'},
  {from: 59, duration: 9, kicker: 'RESULTS', title: '100 / 100 routes', caption: 'The navigation tests built one hundred routes out of one hundred. In a live run, the bot crossed a door in 44 control frames with zero replans.', kind: 'split'},
  {from: 68, duration: 8, kicker: 'NEXT MILESTONE', title: 'Target tracking +\npredictive shooting', caption: 'Next: choose a target, predict its movement, and shoot ahead. One more step toward a fully autonomous winning run.', kind: 'game'},
] as const;

const Badge = () => <div className="badge">ENGLISH EDITION&nbsp;&nbsp;•&nbsp;&nbsp;NO VOICE-OVER</div>;

const ActionClip = ({view}: {view: 'game' | 'model'}) => <div className="media-frame model-frame">
  <Video
    className={view === 'game' ? 'enemy-game-video' : 'enemy-model-video'}
    src={staticFile(view === 'game' ? 'enemy-gameplay.mp4' : 'enemy-model.mp4')}
    muted
    loop
  />
  <div className="scan" />
</div>;

const Scene = ({scene}: {scene: (typeof scenes)[number]}) => {
  const frame = useCurrentFrame();
  const enter = interpolate(frame, [0, 14], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const exit = interpolate(frame, [scene.duration * FPS - 12, scene.duration * FPS], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <AbsoluteFill className="scene" style={{opacity: Math.min(enter, exit)}}>
    <div className="glow glow-a"/><div className="glow glow-b"/><Badge />
    <div className="header"><div className="kicker">{scene.kicker}</div><div className="title">{scene.title}</div></div>
    <div className="visual visual-model"><ActionClip view={scene.from < 33 ? 'game' : 'model'} /></div>
    <div className="caption"><span>{scene.caption}</span></div>
    <div className="progress"><div style={{width: `${((scene.from + frame / FPS) / 76) * 100}%`}} /></div>
  </AbsoluteFill>;
};

const Reel = () => <AbsoluteFill className="reel">{scenes.map((scene) => <Sequence key={scene.from} from={scene.from * FPS} durationInFrames={scene.duration * FPS}><Scene scene={scene} /></Sequence>)}</AbsoluteFill>;

export const MyComposition = () => <Composition id="IsaacBotEnglishReel" component={Reel} durationInFrames={76 * FPS} fps={FPS} width={1080} height={1920} />;
