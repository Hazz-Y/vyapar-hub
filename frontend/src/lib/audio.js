// Audio playback: Sarvam MP3 (base64) when available, else the browser's speechSynthesis.

let current = null

export function stopAudio() {
  if (current) {
    current.pause()
    current = null
  }
  if (typeof window !== 'undefined' && window.speechSynthesis) window.speechSynthesis.cancel()
}

function speakWithBrowser(text) {
  return new Promise((resolve) => {
    const synth = typeof window !== 'undefined' ? window.speechSynthesis : null
    if (!synth || !text) return resolve('none')
    const u = new SpeechSynthesisUtterance(text.replace(/₹\s?([\d,]+)/g, '$1 rupaye'))
    u.lang = 'hi-IN'
    const hindi = synth.getVoices().find((v) => v.lang?.startsWith('hi'))
    if (hindi) u.voice = hindi
    u.rate = 1
    u.onend = () => resolve('browser')
    u.onerror = () => resolve('browser')
    synth.speak(u)
  })
}

// audio: the backend's speak() result {audio_b64, mime, provider, text}
export async function playSpeech(audio, fallbackText) {
  stopAudio()
  if (audio?.audio_b64) {
    const el = new Audio(`data:${audio.mime || 'audio/mpeg'};base64,${audio.audio_b64}`)
    current = el
    try {
      await el.play()
      await new Promise((resolve) => {
        el.onended = resolve
        el.onerror = resolve
      })
      return 'sarvam'
    } catch {
      // autoplay blocked or decode error: fall through to the browser voice
    }
  }
  return speakWithBrowser(audio?.text || fallbackText)
}
