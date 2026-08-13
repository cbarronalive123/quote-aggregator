import 'package:flutter/material.dart';
import 'form_page.dart';
import 'assistant_page.dart';
import 'splash_screen.dart';
import 'history_page.dart';
import 'api_client.dart';
import 'models.dart';
import 'config.dart';

void main() {
  runApp(const QuoteDriveApp());
}

class QuoteDriveApp extends StatelessWidget {
  const QuoteDriveApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'QuoteDrive',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF4D6BFF),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      home: const SplashScreen(),
    );
  }
}

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  Future<void> _useSavedProfile(BuildContext context) async {
    final api = ApiClient();
    List<Profile> profiles;
    try {
      profiles = await api.fetchProfiles();
    } catch (e) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.toString())));
      return;
    }
    if (!context.mounted) return;
    final chosen = await showModalBottomSheet<Profile>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const ListTile(
              leading: Icon(Icons.person_search),
              title: Text('Choose a saved profile',
                  style: TextStyle(fontWeight: FontWeight.bold)),
            ),
            for (final p in profiles)
              ListTile(
                leading: const Icon(Icons.person),
                title: Text(p.name),
                subtitle: p.id == 'mock'
                    ? const Text('Mock details for testing')
                    : const Text('Your saved details'),
                onTap: () => Navigator.pop(ctx, p),
              ),
          ],
        ),
      ),
    );
    if (chosen != null && context.mounted) {
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => FormPage(initialValues: chosen.values),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('QuoteDrive')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.shield_moon, size: 56, color: Colors.blueAccent),
              const SizedBox(height: 12),
              const Text('Ontario auto insurance, compared',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              const Text(
                'One intake. We fill the same form the website uses and reach '
                'every carrier — online or by phone.',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey, fontSize: 13),
              ),
              const SizedBox(height: 28),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const AssistantPage()),
                  ),
                  icon: const Icon(Icons.assistant),
                  label: const Text('Fill with AI assistant'),
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const FormPage()),
                  ),
                  icon: const Icon(Icons.edit),
                  label: const Text('Fill the form manually'),
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: () => _useSavedProfile(context),
                  icon: const Icon(Icons.person),
                  label: const Text('Fill from saved profile'),
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: () => Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const HistoryPage()),
                  ),
                  icon: const Icon(Icons.history),
                  label: const Text('Quote history'),
                ),
              ),
              const SizedBox(height: 24),
              const Text(
                'Backend: ${AppConfig.apiBaseUrl}',
                style: TextStyle(color: Colors.grey, fontSize: 10),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
