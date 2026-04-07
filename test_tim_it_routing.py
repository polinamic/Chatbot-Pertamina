#!/usr/bin/env python
"""
Test untuk memverifikasi apakah AI bisa mencari TIM IT yang sesuai dengan kebutuhan user
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.rag.services.chat_service import chat
from apps.rag.services.vector_store import VectorStore
from apps.rag.services.embedding import EmbeddingService

# Mock vector store dan embedding service untuk test
class MockVectorStore:
    def search(self, query_embedding, top_k=5, doc_type=None):
        # Return mock results
        return []

class MockEmbeddingService:
    def encode(self, text):
        # Return mock embedding
        return [0.1] * 768
    
    def embed_text(self, text):
        # Method yang dibutuhkan semantic detector
        return self.encode(text)

def test_tim_it_routing():
    """Test apakah AI bisa routing ke TIM IT yang sesuai"""

    # Test cases dengan masalah IT berbeda dan tim yang diharapkan
    test_cases = [
        {
            "question": "Kartu akses pintu tidak bisa dibaca",
            "expected_team": "Access Control Device",
            "description": "Masalah kontrol akses fisik"
        },
        {
            "question": "Saya perlu akses ke VPN untuk bekerja remote",
            "expected_team": "Access Management End User",
            "description": "Masalah akses digital/VPN"
        },
        {
            "question": "Laptop saya rusak secara fisik, layarnya pecah",
            "expected_team": "Hardware Support",
            "description": "Masalah hardware fisik"
        },
        {
            "question": "Aplikasi ERP tidak bisa diakses setelah update",
            "expected_team": "Software Support",
            "description": "Masalah software/aplikasi"
        },
        {
            "question": "Internet di kantor sangat lambat",
            "expected_team": "Network Support",
            "description": "Masalah jaringan"
        },
        {
            "question": "Email saya tidak bisa dikirim",
            "expected_team": "Email/Messaging Support",
            "description": "Masalah email"
        }
    ]

    print("=" * 80)
    print("TESTING: AI Routing ke TIM IT yang Sesuai")
    print("=" * 80)

    # Mock services
    vector_store = MockVectorStore()
    embedding_service = MockEmbeddingService()

    passed = 0
    total = len(test_cases)

    for i, test_case in enumerate(test_cases, 1):
        question = test_case["question"]
        expected_team = test_case["expected_team"]
        description = test_case["description"]

        print(f"\nTest {i}/{total}: {description}")
        print(f"Pertanyaan: {question}")
        print(f"Tim Expected: {expected_team}")

        try:
            # Test dengan session baru
            response = chat(question, vector_store, embedding_service, session_id=f"test_{i}")

            print(f"Response: {response[:200]}...")

            # Cek apakah response mengandung kata-kata yang menunjukkan routing ke tim yang tepat
            response_lower = response.lower()

            # Cek indikator routing
            routing_indicators = [
                expected_team.lower(),
                "tim it" in response_lower,
                "eskalasi" in response_lower,
                "panduan" in response_lower,
                "helpdesk" in response_lower
            ]

            # Untuk test yang lebih ketat, pastikan tim spesifik disebutkan
            team_mentioned = expected_team.lower() in response_lower
            
            # Cek apakah ada indikator routing
            has_routing = any(routing_indicators)

            if has_routing and team_mentioned:
                print("✓ PASS - AI memberikan routing spesifik ke tim yang tepat")
                passed += 1
            elif has_routing:
                print("⚠ PARTIAL - AI memberikan panduan routing tapi tim tidak spesifik")
                passed += 0.5  # partial credit
            else:
                print("✗ FAIL - AI tidak memberikan panduan routing yang jelas")

        except Exception as e:
            print(f"✗ ERROR - Exception: {str(e)}")

    print("\n" + "=" * 80)
    print(f"HASIL TEST: {passed}/{total} passed")
    print("=" * 80)

    if passed >= total * 0.8:  # 80% success rate
        print("✅ KESIMPULAN: AI sudah bisa mencari/mengarahkan ke TIM IT yang sesuai")
        print("   - AI memberikan panduan eskalasi berdasarkan jenis masalah")
        print("   - Routing spesifik ke tim IT yang tepat")
        print("   - Menggunakan knowledge base untuk routing yang akurat")
    elif passed >= total * 0.5:  # 50% success rate
        print("⚠ KESIMPULAN: AI memberikan routing dasar tapi perlu perbaikan spesifisitas")
        print("   - Perlu improve deteksi kategori masalah")
        print("   - Tambahkan lebih banyak data training untuk routing")
    else:
        print("❌ KESIMPULAN: AI belum bisa mencari TIM IT yang sesuai")
        print("   - Perlu implementasi routing berdasarkan kategori masalah")
        print("   - Tambahkan knowledge base untuk tim IT")

    return passed >= total * 0.8

if __name__ == "__main__":
    test_tim_it_routing()