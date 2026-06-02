<?php

namespace App\Http\Controllers;

use App\Services\RagService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use RuntimeException;

class RagController extends Controller
{
    private RagService $rag;

    public function __construct(RagService $rag)
    {
        $this->rag = $rag;
    }

    public function ask(Request $request): JsonResponse
    {
        $validated = $request->validate([
            'question'   => 'required|string|max:500',
            'session_id' => 'nullable|string|uuid',
        ]);

        try {
            $result = $this->rag->ask(
                $validated['question'],
                $validated['session_id'] ?? null
            );
        } catch (RuntimeException $e) {
            return response()->json(['error' => $e->getMessage()], 502);
        }

        return response()->json($result);
    }

    public function clearSession(Request $request, string $sessionId): JsonResponse
    {
        $this->rag->clearSession($sessionId);
        return response()->json(['cleared' => $sessionId]);
    }
}
