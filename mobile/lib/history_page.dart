import 'package:flutter/material.dart';
import 'api_client.dart';
import 'models.dart';

/// History of all processed quote runs, split into "My profiles" (real) and
/// "Fake profiles" tabs — mirrors the website's /history page.
class HistoryPage extends StatefulWidget {
  const HistoryPage({super.key});

  @override
  State<HistoryPage> createState() => _HistoryPageState();
}

class _HistoryPageState extends State<HistoryPage> {
  final ApiClient _api = ApiClient();
  bool _loading = true;
  String? _error;
  List<QuoteRun> _all = [];
  bool _showFake = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final runs = await _api.fetchHistory();
      if (!mounted) return;
      setState(() {
        _all = runs;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  List<QuoteRun> get _visible =>
      _all.where((r) => _showFake ? r.isFake : !r.isFake).toList();

  String _fmt(String iso) {
    if (iso.isEmpty) return '—';
    final dt = DateTime.tryParse(iso)?.toLocal();
    if (dt == null) return iso;
    String two(int n) => n.toString().padLeft(2, '0');
    return '${dt.year}-${two(dt.month)}-${two(dt.day)} '
        '${two(dt.hour)}:${two(dt.minute)}';
  }

  Color _statusColor(String status) {
    if (status == 'quoted_comparable') return Colors.green;
    if (status == 'quoted_non_comparable') return Colors.amber;
    return Colors.grey;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Quote history')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildError()
              : _buildBody(),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off, size: 48, color: Colors.grey),
            const SizedBox(height: 12),
            Text(_error!, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton(onPressed: _load, child: const Text('Retry')),
          ],
        ),
      ),
    );
  }

  Widget _buildBody() {
    final visible = _visible;
    final fakeCount = _all.where((r) => r.isFake).length;
    final realCount = _all.length - fakeCount;
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: SegmentedButton<bool>(
            segments: [
              ButtonSegment(value: false, label: Text('My profiles ($realCount)')),
              ButtonSegment(value: true, label: Text('Fake profiles ($fakeCount)')),
            ],
            selected: {_showFake},
            onSelectionChanged: (s) => setState(() => _showFake = s.first),
          ),
        ),
        Expanded(
          child: visible.isEmpty
              ? const Center(
                  child: Text('No runs recorded here yet.',
                      style: TextStyle(color: Colors.grey)),
                )
              : ListView.builder(
                  padding: const EdgeInsets.fromLTRB(12, 0, 12, 16),
                  itemCount: visible.length,
                  itemBuilder: (context, i) => _runCard(visible[i]),
                ),
        ),
      ],
    );
  }

  Widget _runCard(QuoteRun run) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(run.label ?? 'Automated quote run',
                          style: const TextStyle(
                              fontSize: 15, fontWeight: FontWeight.bold)),
                      const SizedBox(height: 2),
                      Text(_fmt(run.runAt),
                          style: const TextStyle(
                              color: Colors.grey, fontSize: 12)),
                    ],
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text('${run.quotedCount}/${run.outcomes.length} quoted',
                        style: const TextStyle(
                            fontSize: 13, fontWeight: FontWeight.bold)),
                    if (run.profile != null && run.profile!.isNotEmpty)
                      Text(run.profile!,
                          style: const TextStyle(
                              color: Colors.grey, fontSize: 10)),
                  ],
                ),
              ],
            ),
            const Divider(height: 18),
            for (final o in run.outcomes)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(o.brand,
                              style:
                                  const TextStyle(fontWeight: FontWeight.w600)),
                          Text(
                            o.status.replaceAll('_', ' '),
                            style: TextStyle(
                                color: _statusColor(o.status), fontSize: 11),
                          ),
                        ],
                      ),
                    ),
                    Text(
                      o.annualPremium == null
                          ? '—'
                          : '\$${o.annualPremium!.toStringAsFixed(2)}',
                      style: const TextStyle(
                          fontSize: 15, fontWeight: FontWeight.bold),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}
