const bars = [12,18,8,24,32,16,40,22,28,45,34,18,52,30,24,58,42,30,48,25,62,38,28,54,33,20,46,32,16,38,26,18,34,22,14,28,18,12,22,15,10,17,12,8,14,9,7,11];

export function Waveform({ progress = 0, onSeek }: { progress?: number; onSeek?: (ratio: number) => void }) {
  return (
    <button
      className="waveform"
      aria-label="Seek through track"
      onClick={(event) => onSeek?.(event.nativeEvent.offsetX / event.currentTarget.clientWidth)}
      style={{ "--progress": `${Math.max(0, Math.min(progress, 1)) * 100}%` } as React.CSSProperties}
    >
      {bars.map((height, index) => <i key={index} style={{ height }} />)}
    </button>
  );
}
