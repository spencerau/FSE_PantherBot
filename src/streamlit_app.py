import streamlit as st
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from retrieval.unified_rag import UnifiedRAG
from utils.config_loader import load_config


def main():
    st.set_page_config(
        page_title="Fowler Engineering Academic Advisor",
        layout="wide"
    )
    
    st.title("Fowler Engineering Academic Advisor")
    st.caption("AI-powered academic guidance")
    
    if 'rag_system' not in st.session_state:
        with st.spinner("Initializing AI advisor..."):
            st.session_state.rag_system = UnifiedRAG()
    
    if not hasattr(st.session_state.rag_system.answer_question, '__code__') or 'enable_reranking' not in st.session_state.rag_system.answer_question.__code__.co_varnames:
        with st.spinner("Updating AI advisor..."):
            st.session_state.rag_system = UnifiedRAG()
    
    rag = st.session_state.rag_system
    
    with st.sidebar:
        st.header("Your Academic Profile")
        
        programs = [
            "Computer Science",
            "Computer Engineering", 
            "Software Engineering",
            "Electrical Engineering",
            "Data Science"
        ]
        
        student_program = st.selectbox(
            "Select your major:",
            programs,
            key="student_program"
        )
        
        years = ["2022", "2023", "2024", "2025"]
        student_year = st.selectbox(
            "Catalog year (year you entered):",
            years,
            index=3,  # Default to 2025
            key="student_year"
        )
        
        minors = [
            "None",
            "Analytics", 
            "Computer Science",
            "Computer Engineering",
            "Electrical Engineering",
            "Game Development",
            "Information Security Policy"
        ]
        
        student_minor = st.selectbox(
            "Select your minor (optional):",
            minors,
            key="student_minor"
        )
        
        if student_minor == "None":
            student_minor = None
        
        with st.expander("System Status"):
            collections = rag.list_collections()
            st.write(f"**Available collections:** {len(collections)}")
            
            if 'general_knowledge' in collections:
                gen_stats = rag.get_collection_stats('general_knowledge')
                if 'error' not in gen_stats:
                    st.info(f"General knowledge: {gen_stats['points_count']} documents")
            
            if st.button("Clear Cache & Reload", help="Force reload the AI system"):
                if 'rag_system' in st.session_state:
                    del st.session_state.rag_system
                st.rerun()
        
        st.header("AI Settings")
        
        enable_thinking = st.checkbox(
            "Enable AI Thinking Mode",
            value=True,
            help="When enabled, the AI will think through problems more carefully before responding. This may improve answer quality but could be slightly slower.",
            key="enable_thinking"
        )
        
        show_thinking = True
        if enable_thinking:
            config = load_config()
            default_show_thinking = 'deepseek' in config.get('llm', {}).get('model', '').lower()
            
            show_thinking = st.checkbox(
                "Show Thinking Process",
                value=default_show_thinking,
                help="Display the AI's internal reasoning process. Useful for debugging and understanding the AI's thought process.",
                key="show_thinking"
            )
        
        st.subheader("Response Settings")
        use_streaming = st.checkbox(
            "Stream Responses",
            value=True,
            help="Show responses as they're generated for a more interactive experience.",
            key="use_streaming"
        )
        
        enable_reranking = st.checkbox(
            "Enable Reranking",
            value=True,
            help="Use AI reranking for better results (slower, ~30s first use).",
            key="enable_reranking"
        )
        
        debug_mode = st.checkbox(
            "Debug Mode",
            value=True,
            help="Show detailed retrieval and reranking information.",
            key="debug_mode"
        )
    
    st.header("Ask Your Academic Questions")
    
    if "messages" not in st.session_state:
        minor_text = f" with a {student_minor} minor/themed inquiry" if student_minor else ""
        st.session_state.messages = [
            {
                "role": "assistant", 
                "content": f"Hello! I'm your AI academic advisor for {student_program} students{minor_text} (catalog year {student_year}). I can help you with:\n\n• Degree requirements and graduation planning\n• Course listings and availability\n• Prerequisites and course sequencing\n• Program-specific information\n• General university knowledge\n\nWhat would you like to know about your academic program?"
            }
        ]
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    if prompt := st.chat_input("Ask about your degree requirements, course listings, or academic planning..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Searching academic catalogs..."):
                try:
                    program_codes = {
                        "Computer Science": "cs",
                        "Computer Engineering": "ce", 
                        "Software Engineering": "se",
                        "Electrical Engineering": "ee",
                        "Data Science": "ds"
                    }
                    program_code = program_codes.get(student_program, "cs")
                    
                    minor_codes = {
                        "Analytics": "analytics",
                        "Computer Science": "cs",
                        "Computer Engineering": "ce",
                        "Electrical Engineering": "ee", 
                        "Game Development": "gamedev", 
                        "Information Security Policy": "isp"
                    }
                    minor_code = minor_codes.get(student_minor) if student_minor else None
                    
                    last_n_messages = rag.config.get('query_router', {}).get('last_n_messages', 4)
                    conversation_history = st.session_state.messages[:-1]
                    if len(conversation_history) > last_n_messages:
                        conversation_history = conversation_history[-last_n_messages:]
                    
                    answer, retrieved_chunks, debug_info = rag.answer_question(
                        prompt,
                        conversation_history=conversation_history,
                        student_program=program_code,
                        student_year=student_year,
                        student_minor=minor_code,
                        top_k=rag.config.get('retrieval', {}).get('final_top_k', 15),  # Use config value
                        enable_thinking=st.session_state.get('enable_thinking', True),
                        show_thinking=st.session_state.get('show_thinking', False),
                        use_streaming=st.session_state.get('use_streaming', True),
                        enable_reranking=st.session_state.get('enable_reranking', rag.config.get('retrieval', {}).get('enable_reranking', True)),  # Default from config
                        return_debug_info=True
                    )
                    
                    def clean_html_for_display(text):
                        if isinstance(text, str):
                            return text.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
                        return text
                    
                    if st.session_state.get('use_streaming', True) and hasattr(answer, '__iter__') and not isinstance(answer, str):
                        response_placeholder = st.empty()
                        full_response = ""
                        
                        for chunk in answer:
                            cleaned_chunk = clean_html_for_display(chunk)
                            full_response += cleaned_chunk
                            response_placeholder.markdown(full_response + "▌")
                        
                        response_placeholder.markdown(full_response)
                        answer = full_response
                    else:
                        cleaned_answer = clean_html_for_display(answer)
                        st.markdown(cleaned_answer)
                    
                    if retrieved_chunks:
                        with st.expander("Sources Used", expanded=False):
                            for i, chunk in enumerate(retrieved_chunks):
                                metadata = chunk.get('metadata', {})
                                collection = chunk.get('collection', '')
                                score = chunk.get('score', 0)
                                rerank_score = chunk.get('rerank_score', score)
                                
                                st.write(f"**Source {i+1}** (Similarity: {score:.3f}, Relevance: {rerank_score:.3f})")
                                st.write(f"Collection: `{collection}`")
                                
                                if metadata:
                                    meta_info = []
                                    if metadata.get('year'):
                                        meta_info.append(f"Year: {metadata['year']}")
                                    if metadata.get('subject'):
                                        meta_info.append(f"Subject: {metadata['subject']}")
                                    if metadata.get('document_type'):
                                        meta_info.append(f"Type: {metadata['document_type']}")
                                    if metadata.get('file_name'):
                                        meta_info.append(f"File: {metadata['file_name']}")
                                    
                                    if meta_info:
                                        st.write(f"Metadata: {', '.join(meta_info)}")
                                
                                text_preview = chunk['text'].replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
                                st.text_area(
                                    f"Content preview:",
                                    text_preview,
                                    height=200,
                                    key=f"source_{i}",
                                    disabled=True
                                )
                                st.divider()
                        
                        if st.session_state.get('debug_mode', False):
                            with st.expander("🔍 Debug Information", expanded=False):
                                st.subheader("Query Processing")
                                st.write(f"**Original Query:** {prompt}")
                                st.write(f"**Student Program:** {student_program}")
                                st.write(f"**Catalog Year:** {student_year}")
                                
                                if debug_info:
                                    st.subheader("RAG Pipeline Debug Output")
                                    for debug_msg in debug_info:
                                        st.code(debug_msg, language="text")
                                
                                st.subheader("Retrieval Details")
                                st.write(f"**Total Chunks Retrieved:** {len(retrieved_chunks)}")
                                
                                dense_scores = [c.get('score_dense', 0) for c in retrieved_chunks if 'score_dense' in c]
                                sparse_scores = [c.get('score_sparse', 0) for c in retrieved_chunks if 'score_sparse' in c]
                                rrf_scores = [c.get('score_rrf', 0) for c in retrieved_chunks if 'score_rrf' in c]
                                rerank_scores = [c.get('rerank_score', 0) for c in retrieved_chunks if 'rerank_score' in c]
                                
                                if dense_scores:
                                    st.write(f"**Dense Retrieval Scores:** {len(dense_scores)} results, top score: {max(dense_scores):.4f}")
                                if sparse_scores:
                                    st.write(f"**Sparse (BM25) Scores:** {len(sparse_scores)} results, top score: {max(sparse_scores):.4f}")
                                if rrf_scores:
                                    st.write(f"**RRF Fusion Scores:** {len(rrf_scores)} results, top score: {max(rrf_scores):.4f}")
                                if rerank_scores:
                                    st.write(f"**Reranking Scores:** {len(rerank_scores)} results, top score: {max(rerank_scores):.4f}")
                                
                                st.subheader("Collection Distribution")
                                collection_counts = {}
                                for chunk in retrieved_chunks:
                                    coll = chunk.get('collection', 'unknown')
                                    collection_counts[coll] = collection_counts.get(coll, 0) + 1
                                
                                for coll, count in collection_counts.items():
                                    st.write(f"- **{coll}**: {count} chunks")
                                
                                st.subheader("Top 5 Chunks Detail")
                                for i, chunk in enumerate(retrieved_chunks[:5]):
                                    st.write(f"**Rank {i+1}:**")
                                    scores_info = []
                                    if 'score_dense' in chunk:
                                        scores_info.append(f"Dense: {chunk['score_dense']:.4f}")
                                    if 'score_sparse' in chunk:
                                        scores_info.append(f"Sparse: {chunk['score_sparse']:.4f}")
                                    if 'score_rrf' in chunk:
                                        scores_info.append(f"RRF: {chunk['score_rrf']:.4f}")
                                    if 'rerank_score' in chunk:
                                        scores_info.append(f"Rerank: {chunk['rerank_score']:.4f}")
                                    
                                    st.write(f"Scores: {', '.join(scores_info)}")
                                    st.write(f"Collection: {chunk.get('collection', 'N/A')}")
                                    st.write(f"Text: {chunk['text'][:150]}...")
                                    st.write("---")
                    
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                
                except Exception as e:
                    error_msg = f"I'm sorry, I encountered an error while processing your question: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("Example Questions")
    
    example_questions = [
        "What are the upper division requirements for my major?",
        "What courses are offered for my program?",
        "What math courses do I need for graduation?",
        "What are the GPA requirements for my program?",
        "What electives can I take for my major?",
        "What are some good classes to take for my junior year?",
    ]
    
    for question in example_questions:
        if st.sidebar.button(question, key=f"example_{question[:20]}", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": question})
            st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.caption("Always verify information with your academic advisor. This AI assistant provides guidance based on available catalogs but official requirements may have updates not reflected here.")


if __name__ == "__main__":
    main()