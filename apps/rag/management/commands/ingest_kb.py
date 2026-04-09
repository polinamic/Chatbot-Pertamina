"""
Management command untuk upload & ingest knowledge base files.

Usage:
    python manage.py ingest_kb --file knowledge_base_it.txt --category TROUBLESHOOT
    python manage.py ingest_kb --file knowledge_base_website_tiket.txt --category ESCALATION
"""

from django.core.management.base import BaseCommand, CommandError
from apps.rag.models import Document, DocumentChunk
from apps.rag.services.embedding import EmbeddingService
import logging
import os

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Ingest knowledge base file ke database dengan proper chunking"

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='File path (relative to media/documents/)'
        )
        parser.add_argument(
            '--category',
            type=str,
            default='TROUBLESHOOT',
            choices=['TROUBLESHOOT', 'ESCALATION'],
            help='Document category/type'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing documents of this category before ingesting'
        )

    def handle(self, *args, **options):
        file_path = os.path.join('media/documents', options['file'])
        category = options['category']
        clear_existing = options['clear']

        # Validate file exists
        if not os.path.exists(file_path):
            raise CommandError(
                f"File tidak ditemukan: {file_path}\n"
                f"File harus berada di media/documents/ directory"
            )

        self.stdout.write(self.style.SUCCESS(f"✓ File ditemukan: {file_path}"))

        # Read file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.stdout.write(f"✓ Content loaded: {len(content)} characters")
        except Exception as e:
            raise CommandError(f"Gagal baca file: {str(e)}")

        # Clear existing if requested
        if clear_existing:
            count = Document.objects.filter(category=category).delete()[0]
            self.stdout.write(
                self.style.WARNING(f"⚠ Deleted {count} existing {category} documents")
            )

        # Initialize embedding service
        try:
            embedding_service = EmbeddingService()
            self.stdout.write("✓ Embedding service initialized")
        except Exception as e:
            raise CommandError(f"Gagal initialize embedding: {str(e)}")

        # Parse based on category
        if category == "TROUBLESHOOT":
            self._ingest_troubleshoot_kb(content, category, embedding_service)
        elif category == "ESCALATION":
            self._ingest_escalation_kb(content, category, embedding_service)

        self.stdout.write(
            self.style.SUCCESS("\n✅ INGESTION COMPLETE!")
        )

    def _ingest_troubleshoot_kb(self, content, category, embedding_service):
        """Parse knowledge_base_it.txt (KATEGORI or KATEGORI: delimiter)"""
        import re

        self.stdout.write(f"\n📥 Starting TROUBLESHOOT KB ingestion...")

        # Split by "KATEGORI " or "KATEGORI:" - flexible parsing
        sections = re.split(r'\nKATEGORI[:\s]+', content)
        count = 0

        for section_idx, section in enumerate(sections):
            section = section.strip()
            if not section:
                continue

            # Full text with KATEGORI prefix (reconstruct)
            if section_idx == 0 and not section.startswith('KATEGORI'):
                # First section before any KATEGORI
                continue
            
            full_text = f"KATEGORI {section}"

            # Parse first line as title
            lines = full_text.split('\n')
            title_match = re.search(r'KATEGORI\s+([^\n]+)', lines[0])
            title = title_match.group(1).strip() if title_match else f"Content_{section_idx}"
            
            # Skip if title is empty or too short
            if not title or len(title) < 3:
                continue

            self.stdout.write(f"  Processing: {title[:60]}...")

            try:
                # Create or update document
                doc, created = Document.objects.get_or_create(
                    title=title,
                    category=category,
                    defaults={
                        'content': full_text,
                        'is_active': True,
                    }
                )

                if not created:
                    doc.content = full_text
                    doc.save()

                # Create embedding chunk
                embedding = embedding_service.embed_text(full_text)

                DocumentChunk.objects.filter(document=doc).delete()
                DocumentChunk.objects.create(
                    document=doc,
                    chunk_index=0,
                    content=full_text,
                    embedding_vector=embedding,
                )

                count += 1
                self.stdout.write(self.style.SUCCESS(f"    ✓ {title[:50]}"))

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"    ✗ Error with {title}: {str(e)}")
                )
                logger.error(f"Failed to ingest {title}: {str(e)}")

        self.stdout.write(f"\n✓ TROUBLESHOOT: {count} documents ingested")

    def _ingest_escalation_kb(self, content, category, embedding_service):
        """Parse knowledge_base_website_tiket.txt (NAMA FORM: delimiter)
        Supports BOTH formats:
        - Format 1 (Old): PANDUAN UI with step-by-step guides
        - Format 2 (New): Direct link format with PANDUAN TIKET + Link (with --- delimiter)
        """
        import re

        self.stdout.write(f"\n📥 Starting ESCALATION KB ingestion...")

        # Normalize line endings for consistent regex matching
        content = content.replace('\r\n', '\n')

        # Robust regex pattern - matches format with --- delimiter reliably
        form_pattern = re.compile(
            r'---\n'  # Mandatory delimiter
            r'NAMA FORM:\s*([^\n]+)\n'
            r'TRIGGER KEYWORD:\s*([^\n]+)\n'
            r'PANDUAN TIKET:\s*([^\n]+)\n'
            r'Link:\s*([^\n]+)',
            re.MULTILINE
        )

        forms = list(form_pattern.finditer(content))
        count = 0

        for form_match in forms:
            nama_form = form_match.group(1).strip()
            trigger_keywords = form_match.group(2).strip() if form_match.group(2) else ""
            panduan_tiket = form_match.group(3).strip() if form_match.group(3) else ""
            link = form_match.group(4).strip() if form_match.group(4) else ""

            self.stdout.write(f"  Processing: {nama_form[:60]}...")

            try:
                # Format 2 (NEW): Direct link format with PANDUAN TIKET
                full_text = f"""NAMA FORM: {nama_form}
TRIGGER KEYWORD: {trigger_keywords}
PANDUAN TIKET: {panduan_tiket}
Link: {link}"""

                # Create or update document
                doc, created = Document.objects.get_or_create(
                    title=nama_form,
                    category=category,
                    defaults={
                        'content': full_text,
                        'is_active': True,
                    }
                )

                if not created:
                    doc.content = full_text
                    doc.save()

                # Create embedding
                embedding = embedding_service.embed_text(full_text)

                DocumentChunk.objects.filter(document=doc).delete()
                DocumentChunk.objects.create(
                    document=doc,
                    chunk_index=0,
                    content=full_text,
                    embedding_vector=embedding,
                )

                count += 1
                self.stdout.write(self.style.SUCCESS(f"    ✓ {nama_form[:50]}"))

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"    ✗ Error with {nama_form}: {str(e)}")
                )
                logger.error(f"Failed to ingest {nama_form}: {str(e)}")

        self.stdout.write(f"\n✓ ESCALATION: {count} forms ingested")
