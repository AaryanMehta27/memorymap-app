const AI_BASE_URL = process.env.NEXT_PUBLIC_AI_API_URL

const USE_MOCK = false // backend is live on localhost:8000

async function callAI(path: string, body: object, token: string) {
  console.log('[ai-client] calling', path, 'token length:', token?.length, 'token preview:', token?.slice(0,20))
  const res = await fetch(`${AI_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const errText = await res.text()
    console.log('[ai-client] error response:', errText)
    throw new Error(`AI service error: ${res.status}`)
  }
  return res.json()
}

export async function analyzePhoto(
  roomId: string,
  imageBase64: string,
  mimeType: string,
  token: string
) {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 1200))
    return {
      tags: [
        {
          label: 'Pill bottle',
          position: 'top shelf, left side',
          confidence: 'high',
          notes: 'Orange prescription bottle',
          canvas_x: 120,
          canvas_y: 80,
        },
        {
          label: 'Reading glasses',
          position: 'nightstand, top surface',
          confidence: 'high',
          notes: 'Black frame glasses in case',
          canvas_x: 280,
          canvas_y: 200,
        },
        {
          label: 'TV remote',
          position: 'couch cushion, right side',
          confidence: 'medium',
          notes: 'Black remote control',
          canvas_x: 420,
          canvas_y: 310,
        },
      ],
    }
  }
  return callAI('/api/vision/analyze', { room_id: roomId, image_base64: imageBase64, image_mime_type: mimeType }, token)
}

export async function queryHome(homeId: string, question: string, token: string) {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 900))
    return {
      answer: `Your pill bottle is on the top shelf on the left side of the bedroom. Your reading glasses are on the nightstand.`,
      source_tags: [
        {
          label: 'Pill bottle',
          position: 'top shelf, left side',
          room_name: 'Bedroom',
          photo_storage_path: null,
        },
        {
          label: 'Reading glasses',
          position: 'nightstand, top surface',
          room_name: 'Bedroom',
          photo_storage_path: null,
        },
      ],
    }
  }
  return callAI('/api/query/ask', { home_id: homeId, question }, token)
}

export async function suggestFloorPlanPositions(
  roomId: string,
  tags: object[],
  canvasWidth: number,
  canvasHeight: number,
  token: string
) {
  if (USE_MOCK) {
    await new Promise((r) => setTimeout(r, 600))
    const cols = Math.ceil(Math.sqrt(tags.length))
    return {
      positions: (tags as { id: string }[]).map((tag, i) => ({
        tag_id: tag.id,
        canvas_x: 60 + (i % cols) * (canvasWidth / (cols + 1)),
        canvas_y: 60 + Math.floor(i / cols) * (canvasHeight / (cols + 1)),
      })),
    }
  }
  return callAI('/api/floorplan/suggest-positions', {
    room_id: roomId,
    tags,
    room_width_px: canvasWidth,
    room_height_px: canvasHeight,
  }, token)
}
