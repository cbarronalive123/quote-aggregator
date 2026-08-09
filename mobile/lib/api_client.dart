import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'config.dart';
import 'models.dart';

class ApiException implements Exception {
  final String message;
  ApiException(this.message);
  @override
  String toString() => message;
}

class ApiClient {
  final String baseUrl;
  final http.Client _client;

  ApiClient({String? baseUrl, http.Client? client})
      : baseUrl = baseUrl ?? AppConfig.apiBaseUrl,
        _client = client ?? http.Client();

  Map<String, String> get _headers => {'Content-Type': 'application/json'};

  Uri _uri(String path, [Map<String, String>? query]) =>
      Uri.parse('$baseUrl$path').replace(queryParameters: query);

  Future<dynamic> _send(
    Future<http.Response> Function() run,
  ) async {
    try {
      final res = await run();
      final body = res.body.isEmpty ? null : jsonDecode(res.body);
      if (res.statusCode >= 200 && res.statusCode < 300) return body;
      throw ApiException((body as Map?)?['error']?.toString() ??
          'HTTP ${res.statusCode}');
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException('Cannot reach the server at $baseUrl. '
          'Is the website running? ($e)');
    }
  }

  /// Fetch the intake form schema (the same one the website uses).
  Future<List<Section>> fetchFormSchema() async {
    final body = await _send(() => _client.get(_uri('/api/form-schema')));
    final sections = (body as Map)['sections'] as List;
    return sections
        .map((s) => Section.fromJson(s as Map<String, dynamic>))
        .toList();
  }

  /// Submit the filled form and start the quote aggregation. Returns a job id.
  /// When [simulate] is true the in-app call session is created (no phone calls).
  Future<String> startQuote(Map<String, String> values, {bool simulate = false}) async {
    final body = await _send(() => _client.post(
          _uri('/api/quote'),
          headers: _headers,
          body: jsonEncode({
            'values': values,
            if (simulate) 'simulate': true,
          }),
        ));
    return ((body as Map)['job_id'] ?? '') as String;
  }

  /// In-app simulated call: control actions (answer / reply / end).
  Future<void> callAction(String action, String jobId, {String text = ''}) async {
    await _send(() => _client.post(
          _uri('/api/call'),
          headers: _headers,
          body: jsonEncode({
            'action': action,
            'job_id': jobId,
            if (text.isNotEmpty) 'text': text,
          }),
        ));
  }

  /// Server-Sent Events stream for the in-app call. Yields parsed JSON events:
  /// ringing / start / agent / outcome / end.
  Stream<Map<String, dynamic>> callEvents(String jobId) async* {
    final req = http.Request('GET', _uri('/api/call/sse', {'job_id': jobId}));
    try {
      final res = await _client.send(req);
      final lines = utf8.decoder
          .bind(res.stream)
          .transform(const LineSplitter());
      var buffer = '';
      await for (final line in lines) {
        if (line.isEmpty) {
          if (buffer.startsWith('data: ')) {
            try {
              final decoded =
                  jsonDecode(buffer.substring(6)) as Map<String, dynamic>;
              yield decoded;
            } catch (_) {}
          }
          buffer = '';
        } else {
          buffer += line;
        }
      }
    } catch (_) {
      // stream ended / network error
    }
  }

  /// Poll the aggregation progress/results.
  Future<QuoteJob> pollQuote(String jobId) async {
    final body = await _send(() => _client.get(
          _uri('/api/quote', {'id': jobId}),
        ));
    return QuoteJob.fromJson(body as Map<String, dynamic>);
  }

  /// One turn of the AI form-filling assistant.
  Future<AssistantReply> assistantTurn(
    Map<String, String> filled,
    String utterance, {
    String? asking,
  }) async {
    final body = await _send(() => _client.post(
          _uri('/api/assistant'),
          headers: _headers,
          body: jsonEncode({
            'filled': filled,
            if (asking != null) 'asking': asking,
            'utterance': utterance,
          }),
        ));
    return AssistantReply.fromJson(body as Map<String, dynamic>);
  }
}
