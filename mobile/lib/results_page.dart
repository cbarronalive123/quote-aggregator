import 'dart:async';
import 'package:flutter/material.dart';
import 'api_client.dart';
import 'models.dart';

/// Shows the aggregated quotes from the website's `/api/quote` job. Polls the
/// backend until the aggregation is complete, then lists quotes sorted by
/// annual cost with coverage differences shown before price.
class ResultsPage extends StatefulWidget {
  final String jobId;
  const ResultsPage({super.key, required this.jobId});

  @override
  State<ResultsPage> createState() => _ResultsPageState();
}

class _ResultsPageState extends State<ResultsPage> {
  final ApiClient _api = ApiClient();
  QuoteJob? _job;
  String? _error;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _poll();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _poll() {
    _timer = Timer.periodic(const Duration(milliseconds: 900), (_) async {
      try {
        final job = await _api.pollQuote(widget.jobId);
        if (!mounted) return;
        setState(() => _job = job);
        if (job.status == 'complete') _timer?.cancel();
      } catch (e) {
        if (!mounted) return;
        _timer?.cancel();
        setState(() => _error = e.toString());
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final job = _job;
    return Scaffold(
      appBar: AppBar(title: const Text('Your quotes')),
      body: _error != null
          ? Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Text(_error!, textAlign: TextAlign.center),
              ),
            )
          : job == null
              ? const Center(child: CircularProgressIndicator())
              : job.status != 'complete'
                  ? _buildProgress(job)
                  : _buildResults(job),
    );
  }

  Widget _buildProgress(QuoteJob job) {
    final label = job.progressLabel;
    final attempt = job.progressAttempt;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(height: 20),
            Text(
              'Reaching every carrier… ${job.progress}/${job.total}',
              style: const TextStyle(fontSize: 16),
            ),
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(999),
              child: LinearProgressIndicator(
                value: job.percentFraction,
                minHeight: 10,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              label != null
                  ? '${job.progressPercent ?? 0}% · Now: $label'
                      '${attempt != null && attempt > 1 ? ' (attempt $attempt)' : ''}'
                  : 'Direct writers, brokers, aggregators and specialty markets are being contacted.',
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.grey, fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResults(QuoteJob job) {
    final quoted = job.outcomes.where((o) => o.isQuoted).toList()
      ..sort((a, b) => (a.annualPremium ?? 0).compareTo(b.annualPremium ?? 0));
    final others = job.outcomes.where((o) => !o.isQuoted).toList();

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text('Sorted by annual cost. Coverage differences are listed '
            'before price — the lowest number isn\'t called the "best" without '
            'showing what differs.',
            style: TextStyle(color: Colors.grey, fontSize: 12)),
        const SizedBox(height: 12),
        if (quoted.isEmpty)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 24),
            child: Text('No comparable quotes returned yet.'),
          ),
        for (final q in quoted)
          Card(
            margin: const EdgeInsets.only(bottom: 10),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(q.brand,
                                style: const TextStyle(
                                    fontSize: 16, fontWeight: FontWeight.bold)),
                            if (q.quoteId != null)
                              Text(q.quoteId!,
                                  style: const TextStyle(
                                      color: Colors.grey, fontSize: 11)),
                          ],
                        ),
                      ),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Text(
                            q.annualPremium == null
                                ? '—'
                                : '\$${q.annualPremium!.toStringAsFixed(2)}',
                            style: const TextStyle(
                                fontSize: 18, fontWeight: FontWeight.bold),
                          ),
                          Text(
                            q.monthlyPremium == null
                                ? ''
                                : '\$${q.monthlyPremium!.toStringAsFixed(2)}/mo',
                            style: const TextStyle(
                                color: Colors.grey, fontSize: 12),
                          ),
                        ],
                      ),
                    ],
                  ),
                  if (q.coverageNotes != null) ...[
                    const SizedBox(height: 8),
                    Text(q.coverageNotes!,
                        style: const TextStyle(
                            color: Colors.grey, fontSize: 12)),
                  ],
                  const SizedBox(height: 6),
                  Text(
                    q.status == 'quoted_comparable'
                        ? 'Comparable quote · ${q.confidence} confidence'
                        : 'Non-comparable (coverage differs)',
                    style: TextStyle(
                        fontSize: 11,
                        color: q.status == 'quoted_comparable'
                            ? Colors.green
                            : Colors.amber),
                  ),
                ],
              ),
            ),
          ),
        if (others.isNotEmpty) ...[
          const SizedBox(height: 8),
          const Text('Not quoted this run',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold)),
          for (final o in others)
            ListTile(
              dense: true,
              leading: const Icon(Icons.info_outline, size: 20),
              title: Text(o.brand,
                  style: const TextStyle(fontSize: 13)),
              subtitle: Text(o.status,
                  style: const TextStyle(fontSize: 11, color: Colors.grey)),
            ),
        ],
      ],
    );
  }
}
