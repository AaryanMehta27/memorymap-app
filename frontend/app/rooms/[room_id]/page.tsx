// TODO: Room detail page — show room photo, tags, floor plan canvas (Konva.js),
// allow editing tags, re-analyzing photo, updating positions.
export default function RoomDetailPage({ params }: { params: { room_id: string } }) {
  return <div>Room Detail: {params.room_id}</div>;
}
