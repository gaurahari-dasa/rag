<?php

// Add these lines to routes/api.php (inside or outside a middleware group as needed).
// Laravel 8+: the Http facade's timeout() is available and Http::delete() works fine.

use App\Http\Controllers\RagController;
use Illuminate\Support\Facades\Route;

Route::post('/rag/ask', [RagController::class, 'ask']);
Route::delete('/rag/session/{sessionId}', [RagController::class, 'clearSession']);
