<?php

namespace App\Services;

use Illuminate\Http\Client\RequestException;
use Illuminate\Support\Facades\Http;
use RuntimeException;

class RagService
{
    private string $baseUrl;
    private string $connection;

    public function __construct()
    {
        $this->baseUrl    = rtrim(config('services.rag.url', 'http://localhost:8001'), '/');
        $this->connection = config('services.rag.connection', '');
    }

    /**
     * @return array{answer: string, sql: string, rows: array, session_id: string, connection: string}
     * @throws RuntimeException
     */
    public function ask(string $question, ?string $sessionId = null): array
    {
        $payload = ['question' => $question, 'session_id' => $sessionId];

        if ($this->connection !== '') {
            $payload['connection'] = $this->connection;
        }

        try {
            $response = Http::timeout(60)->post("{$this->baseUrl}/ask", $payload);
            $response->throw();
        } catch (RequestException $e) {
            throw new RuntimeException(
                'RAG service error: ' . ($e->response->json('detail') ?? $e->getMessage())
            );
        }

        return $response->json();
    }

    public function clearSession(string $sessionId): void
    {
        Http::timeout(10)->delete("{$this->baseUrl}/session/{$sessionId}");
    }

    /**
     * @return array{text: string}
     * @throws RuntimeException
     */
    public function transcribe(\Illuminate\Http\UploadedFile $audio): array
    {
        try {
            $response = Http::timeout(60)
                ->attach('audio', $audio->getContent(), $audio->getClientOriginalName(), [
                    'Content-Type' => $audio->getMimeType() ?? 'audio/webm',
                ])
                ->post("{$this->baseUrl}/transcribe");
            $response->throw();
        } catch (RequestException $e) {
            throw new RuntimeException(
                'Transcription error: ' . ($e->response->json('detail') ?? $e->getMessage())
            );
        }

        return $response->json();
    }
}
