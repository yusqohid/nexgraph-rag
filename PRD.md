# Product Requirements Document (PRD): NexusGraph RAG Engine

## 1. Ringkasan Eksekutif & Tujuan Proyek
**NexusGraph** adalah mesin pencari dan penalaran dokumen berstandar produksi yang menggabungkan pencarian semantik (Vector Search), pencarian kata kunci (Full-Text Search), dan penalaran relasional (Knowledge Graph). Sistem ini dirancang untuk menjawab pertanyaan kompleks lintas dokumen (*multi-hop queries*) dengan sitasi yang dapat diverifikasi dan tingkat halusinasi minimal.

### Tujuan Pembelajaran & Engineering:
1. Membangun *baseline* Vector RAG dan membuktikan secara kuantitatif batas kemampuannya pada pertanyaan relasional.
2. Mengimplementasikan ekstraksi struktur data graf (`Node` & `Edge`) dari teks tidak terstruktur menggunakan *Structured Output* LLM.
3. Menguasai teknik *Hybrid Retrieval* (Vector + Keyword + Graph Traversal) dan *Context Reranking*.
4. Menerapkan pengujian kualitas AI otomatis (evaluasi metrik *Faithfulness* dan *Context Recall*).

---

## 2. Masalah yang Diselesaikan (Problem Statement)
Sistem RAG berbasis vektor tradisional gagal menangani dua skenario kritis:
1. **Kueri Multi-Hop (Lintas Dokumen):** Ketika jawaban membutuhkan penyambungan fakta dari Dokumen A (`Entitas X -> Entitas Y`) dan Dokumen B (`Entitas Y -> Entitas Z`), pencarian vektor gagal menarik Dokumen B karena tidak memiliki kemiripan kosakata langsung dengan `Entitas X`.
2. **Fragmentasi Entitas:** Nama entitas yang ditulis berbeda (misal: *"PT Telekomunikasi Indonesia"*, *"Telkom"*, *"TLKM"*) dianggap sebagai konteks yang terpisah tanpa adanya resolusi entitas.

---

## 3. Target Pengguna & Use Case Utama
Sebagai proyek portofolio dan eksperimen *AI Engineering*, studi kasus data yang digunakan adalah **Dokumen Audit Kepatuhan, Kontrak Vendor, dan Laporan Proyek Internal** (atau kumpulan jurnal/dokumentasi teknis).

* **Use Case 1 (Faktual Tunggal - Vector/BM25):** *"Berapa nilai kontrak maksimal untuk pengadaan server di tahun 2025?"*
* **Use Case 2 (Relasional 2-Hop - GraphRAG):** *"Proyek mana saja yang berisiko terdampak jika Vendor X mengalami kebangkrutan, dan siapa manajer yang bertanggung jawab?"*
* **Use Case 3 (Audit Sitasi):** Pengguna dapat melacak setiap klaim kalimat pada jawaban kembali ke ID paragraf dan dokumen aslinya.

---

## 4. Spesifikasi Fitur (MoSCoW Prioritization)

### Must-Have (MVP - Fase 1 s.d. Fase 3)
* **M1 - Document Ingestion API:** Menerima dokumen Markdown/PDF, memotongnya menjadi *chunks* bertingkat, dan menyimpannya ke database.
* **M2 - Asynchronous Graph Extractor:** *Background worker* yang mengekstrak entitas (`Person`, `Organization`, `Project`, `Risk`, `Technology`) dan relasinya menggunakan validasi skema ketat (Pydantic).
* **M3 - Entity Resolution Dasar:** Menggabungkan entitas duplikat menggunakan kombinasi pencocokan teks yang dinormalisasi dan kemiripan vektor deskripsi.
* **M4 - Hybrid Query Engine:** Mendukung 3 mode kueri melalui parameter API (`mode = "vector" | "hybrid" | "graph"`) agar performa tiap arsitektur dapat dibandingkan secara langsung.
* **M5 - Strict Grounded Citation:** Setiap respons wajib menyertakan referensi `[chunk_id]` yang valid.

### Should-Have (Fase 4)
* **S1 - Cross-Encoder Reranking:** Menyaring kandidat *chunk* dan *subgraph* menjadi Top-K konteks paling relevan sebelum dikirim ke LLM utama.
* **S2 - Adaptive Query Router:** Klasifikator otomatis yang menentukan apakah pertanyaan pengguna cukup dijawab dengan jalur `hybrid` cepat atau butuh jalur `graph` mendalam.
* **S3 - Automated Eval Pipeline:** Skrip CLI untuk menjalankan **20 pertanyaan uji (*Golden Dataset*: 10 soal *single-hop* faktual + 10 soal *multi-hop* relasional)** dan mencetak skor perbandingan antara mode `vector`, `hybrid`, dan `graph`.

### Could-Have (Eksplorasi Lanjutan)
* **C1 - Community Summarization:** Pengelompokan klaster graf untuk menjawab pertanyaan rangkuman tematik tingkat tinggi.
* **C2 - Redis Semantic Cache:** Menyimpan jawaban untuk pertanyaan yang maknanya identik.

### Won't-Have (Di Luar Cakupan Saat Ini)
* Antarmuka pengguna (UI) kompleks — interaksi difokuskan pada REST API, Swagger UI, dan CLI.
* *Fine-tuning* model bahasa sendiri.

---

## 5. Non-Functional Requirements & Target Metrik
1. **Latensi Query (Read Path):**
   * Mode `vector` / `hybrid`: $P95 < 2.0\text{ detik}$ (hingga token pertama / TTFT).
   * Mode `graph` (2-hop): $P95 < 4.5\text{ detik}$.
2. **Kualitas & Akurasi (Diukur pada Golden Dataset):**
   * *Faithfulness Score* $\ge 0.90$ (tidak mengarang fakta di luar konteks).
   * Peningkatan *Context Recall* pada pertanyaan *multi-hop* minimal $+25\%$ dibandingkan mode `vector` biasa.
3. **Ketahanan Ingestion:** Kegagalan ekstraksi graf pada satu *chunk* tidak boleh menghentikan pemrosesan dokumen secara keseluruhan (*graceful degradation* & *retry mechanism*).
