import 'package:flutter/material.dart';
import 'form_page.dart';
import 'assistant_page.dart';
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
      home: const HomePage(),
    );
  }
}

class HomePage extends StatelessWidget {
  const HomePage({super.key});

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
