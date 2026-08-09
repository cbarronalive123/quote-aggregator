/// Mirrors the website's form schema (`website/lib/formSchema.ts`) and the
/// quote result schema (`website/lib/types.ts`). Kept in sync so the app can
/// render the exact same intake form the website uses.

class FieldDef {
  final String key;
  final String label;
  final String type; // text | email | tel | number | date | select
  final List<String> options;
  final bool required;
  final String? placeholder;

  FieldDef({
    required this.key,
    required this.label,
    required this.type,
    this.options = const [],
    this.required = false,
    this.placeholder,
  });

  factory FieldDef.fromJson(Map<String, dynamic> json) => FieldDef(
        key: json['key'] as String,
        label: json['label'] as String,
        type: (json['type'] ?? 'text') as String,
        options: ((json['options'] ?? const []) as List).cast<String>(),
        required: (json['required'] ?? false) as bool,
        placeholder: json['placeholder'] as String?,
      );
}

class Section {
  final String id;
  final String title;
  final String description;
  final List<FieldDef> fields;

  Section({
    required this.id,
    required this.title,
    required this.description,
    required this.fields,
  });

  factory Section.fromJson(Map<String, dynamic> json) => Section(
        id: json['id'] as String,
        title: json['title'] as String,
        description: json['description'] as String,
        fields: ((json['fields'] ?? const []) as List)
            .map((f) => FieldDef.fromJson(f as Map<String, dynamic>))
            .toList(),
      );
}

/// A pre-filled intake profile ("saved profile" shortcut). `values` is keyed by
/// the same field keys as the form schema.
class Profile {
  final String id;
  final String name;
  final Map<String, String> values;

  Profile({required this.id, required this.name, required this.values});

  factory Profile.fromJson(Map<String, dynamic> json) => Profile(
        id: (json['id'] ?? '') as String,
        name: (json['name'] ?? '') as String,
        values: ((json['values'] ?? const {}) as Map)
            .map((k, v) => MapEntry(k as String, (v ?? '').toString())),
      );
}

class QuoteOutcome {
  final String registryId;
  final String brand;
  final String status;
  final double? annualPremium;
  final double? monthlyPremium;
  final String? quoteId;
  final String? coverageNotes;
  final String confidence;
  final String timestamp;
  final String? evidence;

  QuoteOutcome({
    required this.registryId,
    required this.brand,
    required this.status,
    this.annualPremium,
    this.monthlyPremium,
    this.quoteId,
    this.coverageNotes,
    required this.confidence,
    required this.timestamp,
    this.evidence,
  });

  bool get isQuoted =>
      status == 'quoted_comparable' || status == 'quoted_non_comparable';

  factory QuoteOutcome.fromJson(Map<String, dynamic> json) => QuoteOutcome(
        registryId: (json['registry_id'] ?? '') as String,
        brand: (json['brand'] ?? '') as String,
        status: (json['status'] ?? 'unresolved') as String,
        annualPremium: (json['annual_premium'] as num?)?.toDouble(),
        monthlyPremium: (json['monthly_premium'] as num?)?.toDouble(),
        quoteId: json['quote_id'] as String?,
        coverageNotes: json['coverage_notes'] as String?,
        confidence: (json['confidence'] ?? 'low') as String,
        timestamp: (json['timestamp'] ?? '') as String,
        evidence: json['evidence'] as String?,
      );
}

class QuoteJob {
  final String jobId;
  final String status; // running | complete
  final int progress;
  final int total;
  final List<QuoteOutcome> outcomes;

  QuoteJob({
    required this.jobId,
    required this.status,
    required this.progress,
    required this.total,
    this.outcomes = const [],
  });

  double get fraction => total == 0 ? 0 : (progress / total).clamp(0.0, 1.0);

  factory QuoteJob.fromJson(Map<String, dynamic> json) => QuoteJob(
        jobId: (json['job_id'] ?? '') as String,
        status: (json['status'] ?? 'running') as String,
        progress: (json['progress'] ?? 0) as int,
        total: (json['total'] ?? 0) as int,
        outcomes: ((json['outcomes'] ?? const []) as List)
            .map((o) => QuoteOutcome.fromJson(o as Map<String, dynamic>))
            .toList(),
      );
}

class AssistantReply {
  final String reply;
  final Map<String, String> filled;
  final String? nextField;
  final bool done;

  AssistantReply({
    required this.reply,
    required this.filled,
    this.nextField,
    required this.done,
  });

  factory AssistantReply.fromJson(Map<String, dynamic> json) => AssistantReply(
        reply: (json['reply'] ?? '') as String,
        filled: ((json['filled'] ?? const {}) as Map)
            .map((k, v) => MapEntry(k as String, v as String)),
        nextField: json['next_field'] as String?,
        done: (json['done'] ?? false) as bool,
      );
}
