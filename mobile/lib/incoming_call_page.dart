import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;
import 'api_client.dart';
import 'results_page.dart';

/// The free in-app "phone call": after submit the server pushes an incoming
/// call over the internet (SSE). The app shows a ringing screen with Answer /
/// End, then runs the AI quote agent (speaking each line via TTS) while the user
/// answers as the insurance agent (spoken replies via speech-to-text). On end it
/// navigates to the aggregated quotes.
class IncomingCallPage extends StatefulWidget {
  final String jobId;
  const IncomingCallPage({super.key, required this.jobId});

  @override
  State<IncomingCallPage> createState() => _IncomingCallPageState();
}

enum _Phase { ringing, active }

class _IncomingCallPageState extends State<IncomingCallPage> {
  final ApiClient _api = ApiClient();
  final FlutterTts _tts = FlutterTts();
  final stt.SpeechToText _speech = stt.SpeechToText();

  _Phase _phase = _Phase.ringing;
  String _agentText = '';
  bool _listening = false;
  bool _speechAvailable = false;
  bool _sending = false;
  StreamSubscription<Map<String, dynamic>>? _sub;

  @override
  void initState() {
    super.initState();
    _initVoice();
    _listen();
  }

  @override
  void dispose() {
    _sub?.cancel();
    _tts.stop();
    _speech.stop();
    super.dispose();
  }

  Future<void> _initVoice() async {
    try {
      await _tts.setLanguage('en-US');
      await _tts.setSpeechRate(0.45);
      await _tts.awaitSpeakCompletion(true);
      _tts.setCompletionHandler(() {
        // The AI finished speaking its line -> start listening for the user.
        if (mounted && _phase == _Phase.active) _startListening();
      });
    } catch (_) {}
    try {
      _speechAvailable = await _speech.initialize(onStatus: (_) {}, onError: (_) {});
    } catch (_) {
      _speechAvailable = false;
    }
  }

  Future<void> _listen() async {
    _sub = _api.callEvents(widget.jobId).listen((e) => _onEvent(e));
  }

  void _onEvent(Map<String, dynamic> e) {
    if (!mounted) return;
    switch (e['type']) {
      case 'ringing':
        setState(() => _phase = _Phase.ringing);
        break;
      case 'start':
        setState(() => _phase = _Phase.active);
        break;
      case 'agent':
        final finalLine = e['final'] == true;
        setState(() => _agentText = (e['text'] ?? '') as String);
        if (!finalLine) {
          _tts.stop();
          _tts.speak((e['text'] ?? '') as String);
        } else {
          // final line -> just speak it; the server will send outcome/end.
          _tts.stop();
          _tts.speak((e['text'] ?? '') as String);
        }
        break;
      case 'outcome':
        break;
      case 'end':
        _endAndNavigate();
        break;
    }
  }

  Future<void> _startListening() async {
    if (!_speechAvailable || _listening || _sending) return;
    setState(() {
      _listening = true;
    });
    try {
      await _speech.listen(
        onResult: (r) {
          final words = r.recognizedWords;
          if (r.finalResult) {
            _sendReply(words);
          }
        },
        onSoundLevelChange: (_) {},
        listenOptions: stt.SpeechListenOptions(
          listenFor: const Duration(seconds: 15),
          localeId: 'en_US',
          pauseFor: const Duration(seconds: 2),
        ),
      );
    } catch (_) {
      setState(() => _listening = false);
    }
  }

  Future<void> _sendReply(String text) async {
    if (_sending) return;
    setState(() {
      _sending = true;
      _listening = false;
    });
    try {
      await _speech.stop();
    } catch (_) {}
    try {
      await _api.callAction('reply', widget.jobId, text: text.trim());
    } catch (_) {}
    if (mounted) setState(() => _sending = false);
  }

  Future<void> _answer() async {
    try {
      await _api.callAction('answer', widget.jobId);
    } catch (_) {}
    if (mounted) setState(() => _phase = _Phase.active);
  }

  Future<void> _hangUp() async {
    try {
      await _api.callAction('end', widget.jobId);
    } catch (_) {}
    _endAndNavigate();
  }

  void _endAndNavigate() {
    if (!mounted) return;
    _tts.stop();
    _speech.stop();
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => ResultsPage(jobId: widget.jobId)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Column(
          children: [
            const Spacer(flex: 2),
            const CircleAvatar(
              radius: 44,
              backgroundColor: Colors.blueGrey,
              child: Icon(Icons.support_agent, size: 52, color: Colors.white),
            ),
            const SizedBox(height: 16),
            const Text('AI Quote Agent',
                style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold)),
            const SizedBox(height: 6),
            Text(_phase == _Phase.ringing ? 'Incoming call…' : 'Connected',
                style: const TextStyle(color: Colors.grey, fontSize: 14)),
            const Spacer(),
            if (_phase == _Phase.active) ...[
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: Colors.white10,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    _agentText.isEmpty ? '…' : _agentText,
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.white, fontSize: 15, height: 1.4),
                  ),
                ),
              ),
              const SizedBox(height: 10),
              const Text(
                'You are the insurance agent. Answer the AI with the quote details '
                '(e.g. \$1,485 annual, \$123.75 monthly, ref AI-QUOTE-TEST-001).',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey, fontSize: 11),
              ),
            ],
            const Spacer(),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                if (_phase == _Phase.ringing)
                  Column(
                    children: [
                      FloatingActionButton(
                        heroTag: 'answer',
                        backgroundColor: Colors.green,
                        onPressed: _answer,
                        child: const Icon(Icons.call, color: Colors.white),
                      ),
                      const SizedBox(height: 6),
                      const Text('Answer', style: TextStyle(color: Colors.white)),
                    ],
                  )
                else
                  const SizedBox(width: 72),
                Column(
                  children: [
                    FloatingActionButton(
                      heroTag: 'end',
                      backgroundColor: Colors.red,
                      onPressed: _hangUp,
                      child: const Icon(Icons.call_end, color: Colors.white),
                    ),
                    const SizedBox(height: 6),
                    const Text('End', style: TextStyle(color: Colors.white)),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }
}
