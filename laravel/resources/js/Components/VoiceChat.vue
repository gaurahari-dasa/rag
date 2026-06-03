<template>
    <div class="flex flex-col h-full max-w-2xl mx-auto p-4 gap-4">
        <!-- Conversation history -->
        <div ref="historyEl" class="flex-1 overflow-y-auto space-y-3 min-h-0">
            <div v-if="history.length === 0" class="text-center text-gray-400 mt-8 text-sm">
                Ask a question by typing or holding the mic button.
            </div>
            <div
                v-for="(msg, i) in history"
                :key="i"
                :class="msg.role === 'user'
                    ? 'flex justify-end'
                    : 'flex justify-start'"
            >
                <div
                    :class="msg.role === 'user'
                        ? 'bg-indigo-600 text-white rounded-2xl rounded-br-sm'
                        : 'bg-gray-100 text-gray-800 rounded-2xl rounded-bl-sm'"
                    class="max-w-[80%] px-4 py-2 text-sm"
                >
                    {{ msg.content }}
                </div>
            </div>
            <div v-if="loading" class="flex justify-start">
                <div class="bg-gray-100 text-gray-500 rounded-2xl rounded-bl-sm px-4 py-2 text-sm animate-pulse">
                    Thinking…
                </div>
            </div>
        </div>

        <!-- Error banner -->
        <div v-if="error" class="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-2">
            {{ error }}
        </div>

        <!-- Input row -->
        <div class="flex gap-2 items-end">
            <textarea
                v-model="question"
                @keydown.enter.exact.prevent="submit"
                placeholder="Type a question…"
                rows="1"
                class="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
            />
            <button
                @click="submit"
                :disabled="loading || !question.trim()"
                class="shrink-0 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 text-white rounded-xl px-4 py-2 text-sm font-medium transition-colors"
            >
                Send
            </button>
            <!-- Mic button -->
            <button
                @mousedown="startRecording"
                @mouseup="stopRecording"
                @mouseleave="stopRecording"
                @touchstart.prevent="startRecording"
                @touchend.prevent="stopRecording"
                :disabled="loading || !mediaSupported"
                :class="recording
                    ? 'bg-red-500 hover:bg-red-600 animate-pulse'
                    : 'bg-gray-200 hover:bg-gray-300'"
                class="shrink-0 disabled:opacity-40 rounded-xl px-4 py-2 text-lg transition-colors"
                :title="mediaSupported ? 'Hold to speak' : 'Microphone not supported in this browser'"
            >
                🎤
            </button>
        </div>
    </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import axios from 'axios'

const question  = ref('')
const history   = ref([])
const sessionId = ref(sessionStorage.getItem('rag_session_id') ?? null)
const loading   = ref(false)
const error     = ref(null)
const recording = ref(false)
const historyEl = ref(null)
const mediaSupported = ref(false)

let mediaRecorder = null
let audioChunks   = []

onMounted(() => {
    mediaSupported.value = !!navigator.mediaDevices?.getUserMedia && !!window.MediaRecorder
})

async function submit() {
    const q = question.value.trim()
    if (!q || loading.value) return

    error.value = null
    history.value.push({ role: 'user', content: q })
    question.value = ''
    loading.value = true
    await scrollBottom()

    try {
        const { data } = await axios.post('/api/rag/ask', {
            question: q,
            session_id: sessionId.value,
        })
        sessionId.value = data.session_id
        sessionStorage.setItem('rag_session_id', data.session_id)
        history.value.push({ role: 'assistant', content: data.answer })
        speak(data.answer)
    } catch (e) {
        error.value = e.response?.data?.error ?? 'Something went wrong. Please try again.'
    } finally {
        loading.value = false
        await scrollBottom()
    }
}

async function startRecording() {
    if (recording.value || loading.value || !mediaSupported.value) return
    error.value = null
    audioChunks = []

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? 'audio/webm;codecs=opus'
            : 'audio/mp4'

        mediaRecorder = new MediaRecorder(stream, { mimeType })
        mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data) }
        mediaRecorder.onstop = async () => {
            stream.getTracks().forEach(t => t.stop())
            await transcribeAndSubmit(mimeType)
        }
        mediaRecorder.start()
        recording.value = true
    } catch {
        error.value = 'Microphone access denied. Please allow microphone access and try again.'
    }
}

function stopRecording() {
    if (!recording.value || !mediaRecorder) return
    recording.value = false
    mediaRecorder.stop()
}

async function transcribeAndSubmit(mimeType) {
    if (!audioChunks.length) return
    loading.value = true

    const ext  = mimeType.includes('mp4') ? 'm4a' : 'webm'
    const blob = new Blob(audioChunks, { type: mimeType })
    const form = new FormData()
    form.append('audio', blob, `recording.${ext}`)

    try {
        const { data } = await axios.post('/api/rag/transcribe', form, {
            headers: { 'Content-Type': 'multipart/form-data' },
        })
        if (data.text) {
            question.value = data.text
            await submit()
        }
    } catch (e) {
        error.value = e.response?.data?.error ?? 'Transcription failed. Please try again.'
        loading.value = false
    }
}

function speak(text) {
    if (!window.speechSynthesis) return
    window.speechSynthesis.cancel()
    const utt = new SpeechSynthesisUtterance(text)
    utt.lang = 'en-IN'
    window.speechSynthesis.speak(utt)
}

async function scrollBottom() {
    await nextTick()
    if (historyEl.value) historyEl.value.scrollTop = historyEl.value.scrollHeight
}
</script>
