import streamlit as st
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from retrieval.unified_rag import UnifiedRAG
from retrieval.rag_agent import RAGAgent


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
            st.session_state.rag_agent = RAGAgent(st.session_state.rag_system)
    
    rag = st.session_state.rag_system
    agent = st.session_state.rag_agent
    
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
        
        years = ["2022", "2023", "2024"]
        student_year = st.selectbox(
            "Catalog year (year you entered):",
            years,
            index=2,  # Default to 2024
            key="student_year"
        )
        
        with st.expander("System Status"):
            collections = rag.list_collections()
            st.write(f"**Available collections:** {len(collections)}")
            
            if 'general_knowledge' in collections:
                gen_stats = rag.get_collection_stats('general_knowledge')
                if 'error' not in gen_stats:
                    st.info(f"General knowledge: {gen_stats['points_count']} documents")
        
        st.header("AI Settings")
        
        enable_thinking = st.checkbox(
            "Enable AI Thinking Mode",
            value=True,
            help="When enabled, the AI will think through problems more carefully before responding. This may improve answer quality but could be slightly slower.",
            key="enable_thinking"
        )
        
        show_thinking = False
        if enable_thinking:
            show_thinking = st.checkbox(
                "Show Thinking Process",
                value=False,
                help="Display the AI's internal reasoning process. Useful for debugging but may clutter responses.",
                key="show_thinking"
            )
        
        st.subheader("Response Settings")
        use_streaming = st.checkbox(
            "Stream Responses",
            value=True,
            help="Show responses as they're generated for a more interactive experience.",
            key="use_streaming"
        )
    
    st.header("Ask Your Academic Questions")
    
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant", 
                "content": f"Hello! I'm your AI academic advisor for {student_program} students (catalog year {student_year}). I can help you with:\n\n• Degree requirements and graduation planning\n• Course listings and availability\n• Prerequisites and course sequencing\n• Program-specific information\n• General university knowledge\n\nWhat would you like to know about your academic program?"
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
                    
                    answer, context, retrieved_chunks = agent.answer(
                        prompt, 
                        program_code, 
                        student_year,
                        top_k=None,
                        rerank_top_k=None,
                        enable_thinking=st.session_state.get('enable_thinking', True),
                        show_thinking=st.session_state.get('show_thinking', False),
                        use_streaming=st.session_state.get('use_streaming', True)
                    )
                    
                    if st.session_state.get('use_streaming', True) and hasattr(answer, '__iter__') and not isinstance(answer, str):
                        response_placeholder = st.empty()
                        full_response = ""
                        
                        for chunk in answer:
                            full_response += chunk
                            response_placeholder.markdown(full_response + "▌")
                        
                        response_placeholder.markdown(full_response)
                        answer = full_response
                    else:
                        st.markdown(answer)
                    
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
                                
                                text_preview = chunk['text'][:200] + "..." if len(chunk['text']) > 200 else chunk['text']
                                st.text_area(
                                    f"Content preview:",
                                    text_preview,
                                    height=100,
                                    key=f"source_{i}",
                                    disabled=True
                                )
                                st.divider()
                    
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
        "Can you explain the capstone project requirements?",
        "What electives can I take for my major?",
        "How do I apply for graduation?",
        "What are the admission requirements for graduate programs?"
    ]
    
    for question in example_questions:
        if st.sidebar.button(question, key=f"example_{question[:20]}", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": question})
            st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.caption("Always verify information with your academic advisor. This AI assistant provides guidance based on available catalogs but official requirements may have updates not reflected here.")


if __name__ == "__main__":
    main()