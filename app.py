import logging
import os
from fastapi import FastAPI, HTTPException, UploadFile, File, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from asset_intel.storage.database import Neo4jManager
from asset_intel.main import AnalysisEngine
from asset_intel.utils.ai_mapper import CorporateFilingMapper

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("asset_intel.api")

app = FastAPI(
    title="Web Asset Intelligence API",
    description="Passive web footprint ownership mapping and corporate filings engine.",
    version="1.0.0"
)

class AnalyzeRequest(BaseModel):
    domain: str

@app.post("/api/analyze")
async def api_analyze_target(req: AnalyzeRequest):
    logger.info("Received web target analysis request: %s", req.domain)
    if not req.domain or "." not in req.domain:
        raise HTTPException(status_code=400, detail="Invalid domain format")
    
    # Initialize DB Manager
    db_manager = Neo4jManager()
    engine = AnalysisEngine(db_manager)
    
    try:
        # run_analysis will connect, query collectors, save to neo4j, and close the db
        await engine.run_analysis(req.domain)
        return {"status": "success", "message": f"Successfully analyzed target domain {req.domain}"}
    except Exception as exc:
        logger.exception("Analysis failed for target %s", req.domain)
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/api/upload")
async def api_upload_filing(file: UploadFile = File(...)):
    logger.info("Received manual corporate filing upload: %s", file.filename)
    try:
        content = await file.read()
        raw_json_str = content.decode("utf-8")
        
        # Ingest and validate using CorporateFilingMapper
        result = CorporateFilingMapper.map_scc_json(raw_json_str)
        
        # Open database connection to insert filing data
        db = Neo4jManager()
        await db.connect()
        
        total_nodes = 0
        total_edges = 0
        
        try:
            # Create nodes
            for node in result.nodes:
                label = node.__class__.__name__.replace("Model", "")
                key_field = "id"
                if label == "Domain":
                    key_field = "name"
                elif label == "IP":
                    key_field = "address"
                elif label == "Certificate":
                    key_field = "sha256"
                
                node_props = node.model_dump()
                await db.create_node(label, key_field, node_props)
                total_nodes += 1
                
            # Create relationships
            for rel in result.relationships:
                src_lbl, src_key, src_val, r_type, tgt_lbl, tgt_key, tgt_val = rel
                await db.create_relationship(src_lbl, src_key, src_val, r_type, tgt_lbl, tgt_key, tgt_val)
                total_edges += 1
                
        finally:
            await db.close()
            
        return {
            "status": "success",
            "message": f"Filing processed. Created/updated {total_nodes} nodes and {total_edges} relationships.",
            "nodes_count": total_nodes,
            "relationships_count": total_edges
        }
    except Exception as exc:
        logger.exception("Filing upload processing failed")
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/api/graph")
async def api_get_graph():
    logger.info("Retrieving interactive network graph data from Neo4j")
    db = Neo4jManager()
    try:
        await db.connect()
    except Exception as exc:
        logger.error("Failed to connect to Neo4j to retrieve graph: %s", exc)
        raise HTTPException(status_code=503, detail="Database connection failed. Is Neo4j running?")
        
    query = """
    MATCH (n)
    OPTIONAL MATCH (n)-[r]->(m)
    RETURN n, r, m
    """
    
    nodes_map = {}
    edges_map = {}
    
    try:
        async with db.driver.session() as session:
            result = await session.run(query)
            async for record in result:
                n = record["n"]
                r = record["r"]
                m = record["m"]
                
                def parse_node(node):
                    if not node:
                        return None
                    labels = list(node.labels)
                    label = labels[0] if labels else "Unknown"
                    
                    # Determine unique key and identifier
                    if label == "Domain":
                        identity = node.get("name")
                    elif label == "IP":
                        identity = node.get("address")
                    elif label == "Certificate":
                        identity = node.get("sha256")
                    elif label in ("Entity", "Address"):
                        identity = node.get("id")
                    else:
                        identity = node.get("id") or str(node.element_id)
                        
                    if not identity:
                        identity = str(node.element_id)
                        
                    # Extract properties
                    properties = dict(node.items())
                    properties["id"] = identity
                    
                    return {
                        "id": identity,
                        "label": identity,
                        "type": label,
                        "properties": properties
                    }
                
                n_parsed = parse_node(n)
                if n_parsed:
                    nodes_map[n_parsed["id"]] = n_parsed
                    
                if r and m:
                    m_parsed = parse_node(m)
                    if m_parsed:
                        nodes_map[m_parsed["id"]] = m_parsed
                    
                    edge_key = (n_parsed["id"], m_parsed["id"], r.type)
                    if edge_key not in edges_map:
                        edges_map[edge_key] = {
                            "from": n_parsed["id"],
                            "to": m_parsed["id"],
                            "label": r.type,
                            "id": f"{n_parsed['id']}-{r.type}-{m_parsed['id']}"
                        }
                        
        return {
            "nodes": list(nodes_map.values()),
            "edges": list(edges_map.values())
        }
    except Exception as exc:
        logger.exception("Failed to query Neo4j graph")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        await db.close()

# Mount the static files directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
else:
    logger.warning("Static files directory not found at: %s. UI endpoints will not be served.", static_dir)
