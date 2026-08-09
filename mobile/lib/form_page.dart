import 'package:flutter/material.dart';
import 'api_client.dart';
import 'models.dart';
import 'incoming_call_page.dart';

/// The same intake form the website renders, driven by the schema fetched from
/// `/api/form-schema`. On submit it starts the website's quote aggregation and
/// navigates to the results page.
class FormPage extends StatefulWidget {
  const FormPage({super.key});

  @override
  State<FormPage> createState() => _FormPageState();
}

class _FormPageState extends State<FormPage> {
  final ApiClient _api = ApiClient();
  late Future<List<Section>> _future;
  List<Section> _sections = [];
  Map<String, String> _values = {};
  int _sectionIndex = 0;
  bool _loadingSchema = true;
  String? _error;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _future = _api.fetchFormSchema();
    _future.then((sections) {
      setState(() {
        _sections = sections;
        _values = {
          for (final s in sections)
            for (final f in s.fields) f.key: '',
        };
        _loadingSchema = false;
      });
    }).catchError((e) {
      setState(() => _error = e.toString());
    });
  }

  int get _totalFields =>
      _sections.fold(0, (n, s) => n + s.fields.length);

  int get _completedFields {
    var n = 0;
    for (final s in _sections) {
      for (final f in s.fields) {
        if (f.key != 'vin' &&
            f.key != 'trim' &&
            f.key != 'purchase_month' &&
            _values[f.key]?.isNotEmpty == true) {
          n++;
        }
      }
    }
    return n;
  }

  void _setValue(String key, String v) =>
      setState(() => _values[key] = v);

  Future<void> _submit() async {
    setState(() => _submitting = true);
    try {
      // Simulated in-app call (free, no phone network): start the quote job with
      // simulate=true, then open the incoming-call page before the results.
      final jobId = await _api.startQuote(_values, simulate: true);
      if (!mounted) return;
      Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => IncomingCallPage(jobId: jobId)),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.toString())));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Widget _fieldInput(FieldDef field) {
    final value = _values[field.key] ?? '';
    if (field.type == 'select') {
      return DropdownButtonFormField<String>(
        initialValue: value.isEmpty ? null : value,
        decoration: _decoration(field),
        items: [
          for (final o in field.options)
            DropdownMenuItem(value: o, child: Text(o)),
        ],
        onChanged: (v) => _setValue(field.key, v ?? ''),
      );
    }
    return TextFormField(
      initialValue: value,
      keyboardType: _keyboard(field.type),
      decoration: _decoration(field),
      onChanged: (v) => _setValue(field.key, v),
    );
  }

  InputDecoration _decoration(FieldDef field) => InputDecoration(
        isDense: true,
        filled: true,
        hintText: field.placeholder,
        labelText: field.required ? '${field.label} *' : field.label,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      );

  TextInputType? _keyboard(String type) {
    switch (type) {
      case 'number':
        return TextInputType.number;
      case 'email':
        return TextInputType.emailAddress;
      case 'tel':
        return TextInputType.phone;
      case 'date':
        return TextInputType.datetime;
      default:
        return TextInputType.text;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Your quote')),
      body: _loadingSchema
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildError()
              : _buildForm(),
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
            const Text('Could not load the form'),
            const SizedBox(height: 8),
            Text(_error!, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: () {
                setState(() {
                  _error = null;
                  _loadingSchema = true;
                  _future = _api.fetchFormSchema();
                });
                _future.then((sections) {
                  setState(() {
                    _sections = sections;
                    _values = {
                      for (final s in sections)
                        for (final f in s.fields) f.key: '',
                    };
                    _loadingSchema = false;
                  });
                }).catchError((e) => setState(() => _error = e.toString()));
              },
              child: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildForm() {
    final section = _sections[_sectionIndex];
    final isLast = _sectionIndex == _sections.length - 1;
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Get your car insurance quote',
                      style:
                          TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                  Text(
                    '$_completedFields / $_totalFields',
                    style: const TextStyle(color: Colors.grey),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              const Text(
                'We ask once and reuse it to fill every carrier\'s form — online or by phone.',
                style: TextStyle(color: Colors.grey, fontSize: 12),
              ),
              const SizedBox(height: 12),
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: Row(
                  children: [
                    for (var i = 0; i < _sections.length; i++)
                      Padding(
                        padding: const EdgeInsets.only(right: 6),
                        child: ChoiceChip(
                          label: Text(_sections[i].title),
                          selected: i == _sectionIndex,
                          onSelected: (_) =>
                              setState(() => _sectionIndex = i),
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: ListView(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            children: [
              Text(section.title,
                  style: const TextStyle(
                      fontSize: 16, fontWeight: FontWeight.bold)),
              const SizedBox(height: 4),
              Text(section.description,
                  style: const TextStyle(color: Colors.grey, fontSize: 12)),
              const SizedBox(height: 12),
              for (final f in section.fields)
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _fieldInput(f),
                ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              if (_sectionIndex > 0)
                OutlinedButton(
                  onPressed: () =>
                      setState(() => _sectionIndex -= 1),
                  child: const Text('Back'),
                ),
              const Spacer(),
              FilledButton(
                onPressed: _submitting
                    ? null
                    : () {
                        if (isLast) {
                          _submit();
                        } else {
                          setState(() => _sectionIndex += 1);
                        }
                      },
                child: _submitting
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Text(isLast ? 'Get my quotes' : 'Continue'),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
