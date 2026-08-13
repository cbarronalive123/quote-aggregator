import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;
import 'api_client.dart';
import 'results_page.dart';

/// AI-assisted intake: the app asks the user the intake questions one at a time
/// (speaking each question aloud) and fills the same form the website uses.
/// Answers can be typed or spoken via the mic (speech-to-text). When all
/// required fields are captured it submits and shows the aggregated quotes.
class AssistantPage extends StatefulWidget {
  const AssistantPage({super.key});

  @override
  State<AssistantPage> createState() => _AssistantPageState();
}

class _Message {
  final bool fromUser;
  final String text;
  _Message(this.fromUser, this.text);
}

class _AssistantPageState extends State<AssistantPage> {
  final ApiClient _api = ApiClient();
  final TextEditingController _input = TextEditingController();
  final FlutterTts _tts = FlutterTts();
  final stt.SpeechToText _speech = stt.SpeechToText();
  final List<_Message> _messages = [];
  Map<String, String> _filled = {};
  String? _asking;
  bool _loading = true;
  bool _busy = false;
  bool _listening = false;
  bool _speechAvailable = false;
  int _totalFields = 0;

  @override
  void initState() {
    super.initState();
    _initVoice();
    _start();
  }

  @override
  void dispose() {
    _input.dispose();
    _tts.stop();
    _speech.stop();
    super.dispose();
  }

  Future<void> _initVoice() async {
    try {
      await _tts.setLanguage('en-US');
      await _tts.setSpeechRate(0.45);
    } catch (_) {}
    try {
      _speechAvailable =
          await _speech.initialize(onStatus: (_) {}, onError: (_) {});
      if (mounted) setState(() {});
    } catch (_) {
      _speechAvailable = false;
    }
  }

  Future<void> _speak(String text) async {
    try {
      await _tts.stop();
      await _tts.speak(text);
    } catch (_) {}
  }

  Future<void> _start() async {
    setState(() {
      _loading = true;
      _messages.clear();
    });
    try {
      final sections = await _api.fetchFormSchema();
      _totalFields = sections.fold<int>(0, (n, s) => n + s.fields.length);
    } catch (_) {}
    await _turn('Let\'s begin.');
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _turn(String utterance) async {
    setState(() => _busy = true);
    try {
      final reply =
          await _api.assistantTurn(_filled, utterance, asking: _asking);
      setState(() {
        _filled = reply.filled;
        _asking = reply.nextField;
        _messages.add(_Message(true, utterance));
        _messages.add(_Message(false, reply.reply));
      });
      // Speak the assistant's question aloud.
      _speak(reply.reply);
      if (reply.done) {
        await _submitFilled();
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _messages.add(_Message(false,
            'Sorry, I had trouble reaching the server. ${e.toString()}'));
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _submitFilled() async {
    try {
      // Run the real quote aggregation (same as the manual form / website), then
      // show live progress + results.
      final jobId = await _api.startQuote(_filled);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => ResultsPage(jobId: jobId)),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  Future<void> _toggleMic() async {
    if (!_speechAvailable) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text(
              'Speech recognition is not available on this device.')));
      return;
    }
    if (_listening) {
      await _speech.stop();
      setState(() => _listening = false);
      return;
    }
    final ok = await _speech.listen(
      onResult: (r) => setState(() => _input.text = r.recognizedWords),
      onSoundLevelChange: (_) {},
      listenFor: const Duration(seconds: 12),
      localeId: 'en_US',
    );
    if (ok) setState(() => _listening = true);
  }

  void _send() {
    final text = _input.text.trim();
    if (text.isEmpty || _busy) return;
    _input.clear();
    _turn(text);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('AI assistant')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
                  child: Row(
                    children: [
                      const Icon(Icons.assistant,
                          color: Colors.blueAccent),
                      const SizedBox(width: 8),
                      Expanded(
                        child: LinearProgressIndicator(
                          value: _totalFields == 0
                              ? null
                              : (_filled.length / _totalFields)
                                  .clamp(0.0, 1.0),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text(
                        '${_filled.length}/${_totalFields}',
                        style: const TextStyle(
                            color: Colors.grey, fontSize: 12),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _messages.length,
                    itemBuilder: (context, i) {
                      final m = _messages[i];
                      return Align(
                        alignment: m.fromUser
                            ? Alignment.centerRight
                            : Alignment.centerLeft,
                        child: Container(
                          margin: const EdgeInsets.only(bottom: 8),
                          padding: const EdgeInsets.symmetric(
                              horizontal: 14, vertical: 10),
                          decoration: BoxDecoration(
                            color: m.fromUser
                                ? Colors.blue.withOpacity(0.15)
                                : Colors.grey.withOpacity(0.15),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(m.text),
                        ),
                      );
                    },
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
                  child: Row(
                    children: [
                      IconButton(
                        tooltip: _listening
                            ? 'Stop listening'
                            : 'Speak your answer',
                        icon: Icon(
                          _listening ? Icons.stop_circle : Icons.mic,
                          color: _listening ? Colors.red : null,
                        ),
                        onPressed: _busy ? null : _toggleMic,
                      ),
                      Expanded(
                        child: TextField(
                          controller: _input,
                          enabled: !_busy,
                          textInputAction: TextInputAction.send,
                          onSubmitted: (_) => _send(),
                          decoration: const InputDecoration(
                            hintText: 'Type your answer…',
                            border: OutlineInputBorder(),
                            isDense: true,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton.filled(
                        onPressed: _busy ? null : _send,
                        icon: const Icon(Icons.send),
                      ),
                    ],
                  ),
                ),
                // Reserve one row of space below the input bar so it sits a
                // row of text higher than it did.
                const SizedBox(height: 24),
              ],
            ),
    );
  }
}
