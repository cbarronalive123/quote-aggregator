import 'package:flutter_test/flutter_test.dart';

import 'package:all_quote_mobile/main.dart';

void main() {
  testWidgets('App builds and shows the two intake options', (tester) async {
    await tester.pumpWidget(const QuoteDriveApp());
    expect(find.text('Fill with AI assistant'), findsOneWidget);
    expect(find.text('Fill the form manually'), findsOneWidget);
  });
}
