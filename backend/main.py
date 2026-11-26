"""Vivakriss Luxury production backend starter. No automatic bank verification."""
import os, secrets, uuid, hashlib, csv, io
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_UP
from pathlib import Path
from typing import Optional
from sqlalchemy import Boolean, update
from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, String, Integer, Numeric, DateTime, ForeignKey, LargeBinary, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session
from passlib.context import CryptContext
from jose import jwt, JWTError

DATABASE_URL=os.environ.get('DATABASE_URL','sqlite:///./vivakriss_dev.db')
if DATABASE_URL.startswith('postgres://'): DATABASE_URL='postgresql+psycopg://'+DATABASE_URL[len('postgres://'):]
if DATABASE_URL.startswith('postgresql://'): DATABASE_URL='postgresql+psycopg://'+DATABASE_URL[len('postgresql://'):]
engine=create_engine(DATABASE_URL,pool_pre_ping=True,connect_args={'check_same_thread':False} if DATABASE_URL.startswith('sqlite') else {})
SessionLocal=sessionmaker(bind=engine,expire_on_commit=False)
class Base(DeclarativeBase): pass
class Order(Base):
    __tablename__='orders'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    customer_name:Mapped[str]=mapped_column(String(120)); phone:Mapped[str]=mapped_column(String(30)); email:Mapped[str]=mapped_column(String(200)); address:Mapped[str]=mapped_column(String(500))
    kind:Mapped[str]=mapped_column(String(20)); description:Mapped[str]=mapped_column(String(2000))
    total:Mapped[Decimal]=mapped_column(Numeric(12,2)); verified_paid:Mapped[Decimal]=mapped_column(Numeric(12,2),default=0)
    status:Mapped[str]=mapped_column(String(40),default='awaiting_payment')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
class Payment(Base):
    __tablename__='payments'
    id:Mapped[str]=mapped_column(String(36),primary_key=True); order_id:Mapped[str]=mapped_column(ForeignKey('orders.id'))
    amount:Mapped[Decimal]=mapped_column(Numeric(12,2)); transfer_reference:Mapped[str]=mapped_column(String(120))
    status:Mapped[str]=mapped_column(String(30),default='pending_verification')
    receipt_bytes:Mapped[bytes]=mapped_column(LargeBinary); receipt_type:Mapped[str]=mapped_column(String(40))
    submitted_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    reviewed_at:Mapped[Optional[datetime]]=mapped_column(DateTime(timezone=True),nullable=True)
class Product(Base):
    __tablename__='products'
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    name:Mapped[str]=mapped_column(String(160))
    color:Mapped[str]=mapped_column(String(80))
    category:Mapped[str]=mapped_column(String(80))
    image:Mapped[str]=mapped_column(String(255))
    price:Mapped[Optional[Decimal]]=mapped_column(Numeric(12,2),nullable=True)
    stock:Mapped[Optional[int]]=mapped_column(Integer,nullable=True)
    active:Mapped[bool]=mapped_column(Boolean,default=True)

class ProductImage(Base):
    __tablename__='product_images'
    product_id:Mapped[int]=mapped_column(ForeignKey('products.id'),primary_key=True)
    content:Mapped[bytes]=mapped_column(LargeBinary)
    mime:Mapped[str]=mapped_column(String(30))

class OrderItem(Base):
    __tablename__='order_items'
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    order_id:Mapped[str]=mapped_column(ForeignKey('orders.id'),index=True)
    product_id:Mapped[int]=mapped_column(Integer)
    product_name:Mapped[str]=mapped_column(String(160))
    quantity:Mapped[int]=mapped_column(Integer)
    unit_price:Mapped[Decimal]=mapped_column(Numeric(12,2))

class StockMovement(Base):
    __tablename__='stock_movements'
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    product_id:Mapped[int]=mapped_column(Integer,index=True)
    product_name:Mapped[str]=mapped_column(String(160))
    change:Mapped[int]=mapped_column(Integer)
    reason:Mapped[str]=mapped_column(String(60))
    reference:Mapped[str]=mapped_column(String(100),default='')
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class Admin(Base):
    __tablename__='admins'
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
    username:Mapped[str]=mapped_column(String(100),unique=True)
    password_hash:Mapped[str]=mapped_column(String(255))
class BespokeRequest(Base):
    __tablename__='bespoke_requests'
    id:Mapped[str]=mapped_column(String(36),primary_key=True)
    access_hash:Mapped[str]=mapped_column(String(64))
    customer_name:Mapped[str]=mapped_column(String(120))
    phone:Mapped[str]=mapped_column(String(30))
    email:Mapped[str]=mapped_column(String(200))
    address:Mapped[str]=mapped_column(String(500))
    description:Mapped[str]=mapped_column(String(2000))
    quote:Mapped[Optional[Decimal]]=mapped_column(Numeric(12,2),nullable=True)
    order_id:Mapped[Optional[str]]=mapped_column(ForeignKey('orders.id'),nullable=True)
    photo:Mapped[Optional[bytes]]=mapped_column(LargeBinary,nullable=True)
    mime:Mapped[Optional[str]]=mapped_column(String(40),nullable=True)

Base.metadata.create_all(engine)
app=FastAPI(title='Vivakriss Luxury Orders API',docs_url=None if os.getenv('ENVIRONMENT')=='production' else '/docs')
origins=[x.strip() for x in os.getenv('ALLOWED_ORIGINS','http://localhost:8000,http://127.0.0.1:8000').split(',') if x.strip()]
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_methods=['GET','POST','PATCH','DELETE'],allow_headers=['Authorization','Content-Type'])
ctx=CryptContext(schemes=['pbkdf2_sha256'],deprecated='auto')
SECRET=os.getenv('JWT_SECRET','')
if os.getenv('ENVIRONMENT')=='production' and len(SECRET)<32: raise RuntimeError('Set a strong JWT_SECRET (32+ characters)')
if not SECRET: SECRET=secrets.token_urlsafe(40)  # local development sessions only

def db():
    with SessionLocal() as session: yield session

def admin_guard(authorization:Optional[str]=Header(None),session:Session=Depends(db)):
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401,'Admin login required')
    try:
        payload=jwt.decode(authorization[7:],SECRET,algorithms=['HS256'])
        if payload.get('role')!='admin': raise ValueError()
        username=payload['sub']
        user=session.scalar(select(Admin).where(Admin.username==username))
        # Tokens are tied to the current password hash. Password changes revoke all old tokens.
        if not user or not secrets.compare_digest(str(payload.get('pwdv','')),hashlib.sha256(user.password_hash.encode()).hexdigest()):
            raise ValueError()
        return username
    except (JWTError,ValueError,KeyError,TypeError):
        raise HTTPException(401,'Invalid session')

class LoginIn(BaseModel):
    username:str; password:str
class PasswordChangeIn(BaseModel):
    current_password:str
    new_password:str=Field(min_length=12,max_length=128)

class OrderIn(BaseModel):
    customer_name:str=Field(min_length=2,max_length=120)
    phone:str=Field(min_length=7,max_length=30)
    email:str=Field(max_length=200)
    address:str=Field(min_length=5,max_length=500)
    kind:str
    description:str=Field(min_length=3,max_length=2000)
    total:Decimal=Field(gt=0, max_digits=12, decimal_places=2)
class PaymentIn(BaseModel):
    amount:Decimal=Field(gt=0,max_digits=12,decimal_places=2)
    transfer_reference:str=Field(min_length=4,max_length=120)
class Decision(BaseModel):
    approve:bool
class StatusIn(BaseModel):
    status:str

def deposit_due(total): return (total*Decimal('.70')).quantize(Decimal('.01'),rounding=ROUND_UP)

def order_view(o):
    return {'id':o.id,'customer_name':o.customer_name,'phone':o.phone,'email':o.email,'address':o.address,'kind':o.kind,'description':o.description,'total':str(o.total),'verified_paid':str(o.verified_paid),'due_now':str(max(Decimal('0'),(deposit_due(o.total) if o.kind=='bespoke' else o.total)-o.verified_paid)),'balance':str(max(Decimal('0'),o.total-o.verified_paid)),'status':o.status}

@app.get('/health')
def health(): return {'status':'ok'}
@app.get('/payment-instructions')
def instructions(): return {'bank':'Stanbic IBTC Bank','account_name':'Vivakriss Luxury','account_number':'0035278358','ready_made_due_percent':100,'bespoke_deposit_percent':70,'note':'Transfer only after quote/stock confirmation. Receipt is not proof of cleared funds.'}
@app.post('/admin/login')
def login(data:LoginIn,session:Session=Depends(db)):
    user=session.scalar(select(Admin).where(Admin.username==data.username))
    if not user or not ctx.verify(data.password,user.password_hash): raise HTTPException(401,'Invalid credentials')
    token=jwt.encode({'sub':user.username,'role':'admin','pwdv':hashlib.sha256(user.password_hash.encode()).hexdigest(),'exp':datetime.now(timezone.utc)+timedelta(hours=8)},SECRET,algorithm='HS256')
    return {'access_token':token,'token_type':'bearer'}

@app.post('/admin/change-password')
def change_password(data:PasswordChangeIn,who:str=Depends(admin_guard),session:Session=Depends(db)):
    user=session.scalar(select(Admin).where(Admin.username==who))
    if not user or not ctx.verify(data.current_password,user.password_hash):
        raise HTTPException(400,'Current password is incorrect')
    if data.current_password==data.new_password:
        raise HTTPException(422,'New password must differ from the current password')
    if data.new_password.isspace() or data.new_password.strip()!=data.new_password:
        raise HTTPException(422,'Password cannot begin or end with spaces')
    user.password_hash=ctx.hash(data.new_password)
    session.commit()
    return {'message':'Password changed. All previous sessions are invalid. Please sign in again.'}

@app.post('/orders',status_code=201)
def create_order(data:OrderIn,session:Session=Depends(db)):
    if data.kind not in ('ready_made','bespoke'): raise HTTPException(422,'Invalid order type')
    # Production requires an approved server-side quote/catalog price: clients must never set payable amounts.
    raise HTTPException(409,'Quotation confirmation required: create orders through the admin-approved quote endpoint')
class QuoteIn(OrderIn): pass
@app.post('/admin/orders',status_code=201)
def admin_create_order(data:QuoteIn,who:str=Depends(admin_guard),session:Session=Depends(db)):
    if data.kind not in ('ready_made','bespoke'): raise HTTPException(422,'Invalid order type')
    order=Order(id=str(uuid.uuid4()),**data.model_dump(),verified_paid=Decimal('0'),status='awaiting_payment')
    session.add(order);session.commit();return order_view(order)
@app.get('/orders/{order_id}')
def order_status(order_id:str,session:Session=Depends(db)):
    # Never expose customer PII through a public guessable endpoint.
    o=session.get(Order,order_id)
    if not o: raise HTTPException(404,'Order not found')
    return {'id':o.id,'kind':o.kind,'total':str(o.total),'verified_paid':str(o.verified_paid),'status':o.status,'balance':str(max(Decimal('0'),o.total-o.verified_paid))}
@app.post('/orders/{order_id}/receipt',status_code=201)
async def submit_receipt(order_id:str,amount:str,transfer_reference:str,file:UploadFile=File(...),session:Session=Depends(db)):
    o=session.get(Order,order_id)
    if not o: raise HTTPException(404,'Order not found')
    try: value=Decimal(amount)
    except Exception: raise HTTPException(422,'Invalid amount')
    if not value.is_finite() or value<=0 or value>o.total: raise HTTPException(422,'Invalid amount')
    if not (4<=len(transfer_reference)<=120): raise HTTPException(422,'Invalid transfer reference')
    if file.content_type not in ('image/jpeg','image/png','application/pdf'): raise HTTPException(415,'Only JPEG PNG or PDF receipts accepted')
    raw=await file.read(5*1024*1024+1)
    if len(raw)>5*1024*1024 or not raw: raise HTTPException(413,'Receipt must be 1 byte to 5 MB')
    signatures={'image/jpeg':raw.startswith(b'\xff\xd8\xff'),'image/png':raw.startswith(b'\x89PNG\r\n\x1a\n'),'application/pdf':raw.startswith(b'%PDF-')}
    if not signatures[file.content_type]: raise HTTPException(415,'Invalid receipt format')
    p=Payment(id=str(uuid.uuid4()),order_id=o.id,amount=value,transfer_reference=transfer_reference,receipt_bytes=raw,receipt_type=file.content_type)
    session.add(p)
    if o.status in ('awaiting_payment','pending_verification'): o.status='pending_verification'
    session.commit()
    return {'payment_id':p.id,'status':'pending_verification','message':'Receipt received. Payment not yet verified.'}
@app.get('/admin/orders')
def list_orders(who:str=Depends(admin_guard),session:Session=Depends(db)):
    return [order_view(o) for o in session.scalars(select(Order).order_by(Order.created_at.desc())).all()]
@app.get('/admin/payments')
def list_payments(who:str=Depends(admin_guard),session:Session=Depends(db)):
    return [{'id':p.id,'order_id':p.order_id,'amount':str(p.amount),'transfer_reference':p.transfer_reference,'status':p.status} for p in session.scalars(select(Payment)).all()]
@app.get('/admin/payments/{payment_id}/receipt')
def download_receipt(payment_id:str,who:str=Depends(admin_guard),session:Session=Depends(db)):
    p=session.get(Payment,payment_id)
    if not p: raise HTTPException(404,'Payment not found')
    return Response(content=p.receipt_bytes,media_type=p.receipt_type,headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Disposition':'attachment; filename="receipt"'})
@app.post('/admin/payments/{payment_id}/review')
def review_payment(payment_id:str,decision:Decision,who:str=Depends(admin_guard),session:Session=Depends(db)):
    p=session.get(Payment,payment_id)
    if not p: raise HTTPException(404,'Payment not found')
    if p.status!='pending_verification': raise HTTPException(409,'Already reviewed')
    o=session.get(Order,p.order_id)
    if decision.approve and o.verified_paid+p.amount>o.total: raise HTTPException(409,'Payment exceeds order total')
    # Inventory is deducted exactly once when a ready-made order first becomes fully paid.
    if decision.approve and o.kind=='ready_made' and o.verified_paid<o.total and o.verified_paid+p.amount>=o.total:
        items=session.scalars(select(OrderItem).where(OrderItem.order_id==o.id)).all()
        for item in items:
            result=session.execute(update(Product).where(Product.id==item.product_id,Product.active==True,
                Product.stock>=item.quantity).values(stock=Product.stock-item.quantity))
            if result.rowcount!=1:
                session.rollback()
                raise HTTPException(409,f'Insufficient stock for {item.product_name}. Do not approve payment until resolved.')
    if decision.approve and o.kind=='ready_made' and o.verified_paid<o.total and o.verified_paid+p.amount>=o.total:
        for item in items:
            session.add(StockMovement(product_id=item.product_id,product_name=item.product_name,change=-item.quantity,reason='verified_sale',reference=o.id))
    p.status='verified' if decision.approve else 'rejected';p.reviewed_at=datetime.now(timezone.utc)
    if decision.approve:
        o.verified_paid+=p.amount
        if o.status in ('in_production','quality_check','ready_for_dispatch','dispatched','delivered'): pass
        elif o.verified_paid>=o.total: o.status='fully_paid'
        elif o.kind=='bespoke' and o.verified_paid>=deposit_due(o.total): o.status='deposit_verified'
        else: o.status='awaiting_payment'
    session.commit();return order_view(o)
@app.patch('/admin/orders/{order_id}/status')
def set_status(order_id:str,data:StatusIn,who:str=Depends(admin_guard),session:Session=Depends(db)):
    o=session.get(Order,order_id)
    if not o: raise HTTPException(404,'Order not found')
    allowed={'in_production','quality_check','ready_for_dispatch','dispatched','delivered'}
    if data.status not in allowed: raise HTTPException(422,'Invalid status')
    if data.status in {'in_production','quality_check','ready_for_dispatch','dispatched','delivered'} and o.kind=='bespoke' and o.verified_paid<deposit_due(o.total):
        raise HTTPException(409,'Verified 70% deposit required before production')
    if data.status in {'ready_for_dispatch','dispatched','delivered'} and o.verified_paid<o.total:
        raise HTTPException(409,'Full verified payment required before dispatch')
    if o.kind=='ready_made' and o.verified_paid<o.total: raise HTTPException(409,'Full verified payment required')
    o.status=data.status;session.commit();return order_view(o)

# Catalogue endpoints: public read, authenticated administrator writes.
class ProductUpdate(BaseModel):
    price:Optional[Decimal]=Field(default=None,ge=0,max_digits=12,decimal_places=2)
    stock:Optional[int]=Field(default=None,ge=0)
    active:bool=True

def product_view(p):
    return {'id':p.id,'name':p.name,'color':p.color,'category':p.category,'image':('/product-images/'+str(p.id) if p.image=='__uploaded__' else p.image),
            'price':str(p.price) if p.price is not None else None,'stock':p.stock,'active':p.active}

@app.get('/products')
def public_products(session:Session=Depends(db)):
    return [product_view(p) for p in session.scalars(select(Product).where(Product.active==True).order_by(Product.id)).all()]

@app.get('/admin/products')
def admin_products(who:str=Depends(admin_guard),session:Session=Depends(db)):
    return [product_view(p) for p in session.scalars(select(Product).order_by(Product.id)).all()]

class ProductCreate(BaseModel):
    name:str=Field(min_length=2,max_length=160)
    color:str=Field(min_length=1,max_length=80)
    category:str=Field(min_length=1,max_length=80)
    price:Optional[Decimal]=Field(default=None,ge=0,max_digits=12,decimal_places=2)
    stock:Optional[int]=Field(default=None,ge=0)
    active:bool=True

class ProductEdit(BaseModel):
    name:Optional[str]=Field(default=None,min_length=2,max_length=160)
    color:Optional[str]=Field(default=None,min_length=1,max_length=80)
    category:Optional[str]=Field(default=None,min_length=1,max_length=80)
    price:Optional[Decimal]=Field(default=None,ge=0,max_digits=12,decimal_places=2)
    stock:Optional[int]=Field(default=None,ge=0)
    active:bool=True

@app.post('/admin/products',status_code=201)
def create_product(data:ProductCreate,who:str=Depends(admin_guard),session:Session=Depends(db)):
    p=Product(name=data.name.strip(),color=data.color.strip(),category=data.category.strip(),image='',price=data.price,stock=data.stock,active=data.active)
    session.add(p);session.commit();return product_view(p)

@app.patch('/admin/products/{product_id}')
def update_product(product_id:int,data:ProductEdit,who:str=Depends(admin_guard),session:Session=Depends(db)):
    p=session.get(Product,product_id)
    if p is None: raise HTTPException(404,'Product not found')
    old_stock=p.stock
    for field,value in data.model_dump(exclude_unset=True).items():
        if field in ('name','color','category') and value is not None: value=value.strip()
        setattr(p,field,value)
    if 'stock' in data.model_fields_set and old_stock is not None and p.stock is not None and p.stock!=old_stock:
        session.add(StockMovement(product_id=p.id,product_name=p.name,change=p.stock-old_stock,reason='admin_adjustment',reference=who))
    session.commit();return product_view(p)

@app.post('/admin/products/{product_id}/image')
async def upload_product_image(product_id:int,file:UploadFile=File(...),who:str=Depends(admin_guard),session:Session=Depends(db)):
    p=session.get(Product,product_id)
    if p is None: raise HTTPException(404,'Product not found')
    raw=await file.read(5*1024*1024+1)
    if not raw or len(raw)>5*1024*1024: raise HTTPException(413,'Image must be 1 byte to 5 MB')
    mime=file.content_type
    valid=(mime=='image/jpeg' and raw.startswith(b'\xff\xd8\xff')) or (mime=='image/png' and raw.startswith(b'\x89PNG\r\n\x1a\n')) or (mime=='image/webp' and raw.startswith(b'RIFF') and raw[8:12]==b'WEBP')
    if not valid: raise HTTPException(415,'Upload a JPEG, PNG or WebP image')
    picture=session.get(ProductImage,product_id)
    if picture is None: session.add(ProductImage(product_id=product_id,content=raw,mime=mime))
    else: picture.content=raw;picture.mime=mime
    p.image='__uploaded__';session.commit()
    return product_view(p)

@app.get('/product-images/{product_id}')
def get_product_image(product_id:int,session:Session=Depends(db)):
    p=session.get(Product,product_id)
    if p is None or not p.active: raise HTTPException(404,'Image not found')
    picture=session.get(ProductImage,product_id)
    if picture is None: raise HTTPException(404,'Image not found')
    return Response(content=picture.content,media_type=picture.mime,headers={'Cache-Control':'public, max-age=60','X-Content-Type-Options':'nosniff'})

@app.delete('/admin/products/{product_id}')
def archive_product(product_id:int,who:str=Depends(admin_guard),session:Session=Depends(db)):
    p=session.get(Product,product_id)
    if p is None: raise HTTPException(404,'Product not found')
    p.active=False;session.commit();return product_view(p)

# Server-priced ready-made checkout. Never trust a client-provided price or total.
class CartItemIn(BaseModel):
    product_id:int
    quantity:int=Field(ge=1,le=99)
class ReadyOrderIn(BaseModel):
    customer_name:str=Field(min_length=2,max_length=120)
    phone:str=Field(min_length=7,max_length=30)
    email:str=Field(min_length=5,max_length=200)
    address:str=Field(min_length=5,max_length=500)
    items:list[CartItemIn]=Field(min_length=1,max_length=50)

@app.post('/orders/ready-made',status_code=201)
def create_ready_order(data:ReadyOrderIn,session:Session=Depends(db)):
    ids=[i.product_id for i in data.items]
    if len(set(ids))!=len(ids): raise HTTPException(422,'Duplicate products in cart')
    products={p.id:p for p in session.scalars(select(Product).where(Product.id.in_(ids))).all()}
    total=Decimal('0'); lines=[]
    for item in data.items:
        p=products.get(item.product_id)
        if not p or not p.active or p.price is None or p.price<=0 or p.stock is None or p.stock<item.quantity:
            raise HTTPException(409,f'Product {item.product_id} is not available at a confirmed price and quantity')
        total+=p.price*item.quantity
        lines.append(OrderItem(product_id=p.id,product_name=p.name,quantity=item.quantity,unit_price=p.price))
    oid=str(uuid.uuid4())
    order=Order(id=oid,customer_name=data.customer_name,phone=data.phone,email=data.email,
        address=data.address,kind='ready_made',description='; '.join(f'{x.quantity} x {x.product_name}' for x in lines),
        total=total,verified_paid=Decimal('0'),status='awaiting_payment')
    session.add(order)
    for line in lines: line.order_id=oid;session.add(line)
    session.commit()
    return order_view(order)


# Owner-only financial and stock reports. Revenue counts VERIFIED funds, not uploaded receipts.
def report_data(session:Session):
    orders=session.scalars(select(Order).order_by(Order.created_at.desc())).all()
    products=session.scalars(select(Product).order_by(Product.id)).all()
    movements=session.scalars(select(StockMovement).order_by(StockMovement.created_at.desc())).all()
    paid=sum((o.verified_paid or Decimal('0') for o in orders),Decimal('0'))
    outstanding=sum((max(Decimal('0'),o.total-(o.verified_paid or Decimal('0'))) for o in orders),Decimal('0'))
    return {'currency':'NGN','verified_receipts':str(paid),'outstanding_order_balances':str(outstanding),
      'orders_count':len(orders),'orders':[{'id':o.id,'date':o.created_at.isoformat() if o.created_at else '',
        'customer':o.customer_name,'kind':o.kind,'status':o.status,'total':str(o.total),'verified_paid':str(o.verified_paid or 0),
        'outstanding':str(max(Decimal('0'),o.total-(o.verified_paid or Decimal('0'))))} for o in orders],
      'inventory':[{'id':p.id,'name':p.name,'category':p.category,'price':str(p.price) if p.price is not None else '',
        'stock':p.stock,'active':p.active} for p in products],
      'movements':[{'date':m.created_at.isoformat() if m.created_at else '', 'product_id':m.product_id,
        'product':m.product_name,'change':m.change,'reason':m.reason,'reference':m.reference} for m in movements]}

@app.get('/admin/reports/summary')
def admin_report(who:str=Depends(admin_guard),session:Session=Depends(db)):
    return report_data(session)


@app.get('/admin/reports/overview')
def overview(who:str=Depends(admin_guard),session:Session=Depends(db)):
    data=report_data(session)
    tz=timezone(timedelta(hours=1))
    today=datetime.now(tz).date()
    def local_date(dt):
        return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(tz).date()
    periods={'today':today,'week':today-timedelta(days=today.weekday()),'month':today.replace(day=1)}
    receipts={k:Decimal('0') for k in periods}
    by_kind={}
    pending=0
    for amount,status,reviewed,kind in session.execute(select(Payment.amount,Payment.status,Payment.reviewed_at,Order.kind).join(Order,Order.id==Payment.order_id)):
        if status=='pending_verification': pending+=1
        if status=='verified':
            by_kind[kind]=by_kind.get(kind,Decimal('0'))+amount
            if reviewed:
                day=local_date(reviewed)
                for k,start in periods.items():
                    if start<=day<=today: receipts[k]+=amount
    sold={}
    for m in data['movements']:
        if m['reason']=='verified_sale' and m['change']<0:
            sold[m['product_id']]=sold.get(m['product_id'],0)-m['change']
    return {**data,'period_receipts':{k:str(v) for k,v in receipts.items()},'receipts_by_kind':{k:str(v) for k,v in by_kind.items()},'pending_receipts':pending,'sold_by_product':sold,'as_of':datetime.now(tz).isoformat()}

@app.get('/admin/reports/export/{kind}')
def admin_export(kind:str,who:str=Depends(admin_guard),session:Session=Depends(db)):
    data=report_data(session)
    columns={'orders':['date','id','customer','kind','status','total','verified_paid','outstanding'],
      'inventory':['id','name','category','price','stock','active'],
      'movements':['date','product_id','product','change','reason','reference']}
    if kind not in columns: raise HTTPException(404,'Unknown report')
    buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=columns[kind]);writer.writeheader();writer.writerows(data[kind])
    return Response(content='\ufeff'+buf.getvalue(),media_type='text/csv; charset=utf-8',headers={
      'Content-Disposition':f'attachment; filename="vivakriss_{kind}.csv"','Cache-Control':'no-store'})


class BespokeQuote(BaseModel):
    total:Decimal=Field(gt=0,max_digits=12,decimal_places=2)

@app.post('/bespoke-requests',status_code=201)
async def submit_bespoke(customer_name:str=Form(...,min_length=2,max_length=120),phone:str=Form(...,min_length=7,max_length=30),email:str=Form(...,min_length=5,max_length=200),address:str=Form(...,min_length=5,max_length=500),description:str=Form(...,min_length=3,max_length=2000),file:Optional[UploadFile]=File(None),session:Session=Depends(db)):
    raw=None; mime=None
    if file:
        raw=await file.read(5*1024*1024+1); mime=file.content_type
        if not raw or len(raw)>5*1024*1024: raise HTTPException(413,'Photo must be up to 5 MB')
        if not ((mime=='image/jpeg' and raw.startswith(b'\xff\xd8\xff')) or (mime=='image/png' and raw.startswith(b'\x89PNG\r\n\x1a\n')) or (mime=='image/webp' and raw.startswith(b'RIFF') and raw[8:12]==b'WEBP')): raise HTTPException(415,'Invalid image')
    key=secrets.token_urlsafe(32)
    r=BespokeRequest(id=str(uuid.uuid4()),access_hash=hashlib.sha256(key.encode()).hexdigest(),customer_name=customer_name,phone=phone,email=email,address=address,description=description,photo=raw,mime=mime)
    session.add(r);session.commit();return {'id':r.id,'access_key':key}

def bespoke_view(r,session):
    o=session.get(Order,r.order_id) if r.order_id else None
    return {'id':r.id,'quote':str(r.quote) if r.quote is not None else None,'deposit':str(deposit_due(r.quote)) if r.quote is not None else None,'order':order_view(o) if o else None,'status':o.status if o else ('quoted' if r.quote else 'new')}

def customer_request(rid,key,session,lock=False):
    q=select(BespokeRequest).where(BespokeRequest.id==rid)
    r=session.scalar(q.with_for_update() if lock else q)
    if not r or not secrets.compare_digest(r.access_hash,hashlib.sha256(key.encode()).hexdigest()): raise HTTPException(404,'Request not found')
    return r

@app.get('/bespoke-requests/{rid}')
def get_bespoke(rid:str,authorization:str=Header(''),session:Session=Depends(db)):
    return bespoke_view(customer_request(rid,authorization.removeprefix('Bearer '),session),session)

@app.post('/bespoke-requests/{rid}/accept')
def accept_bespoke(rid:str,data:BespokeQuote,authorization:str=Header(''),session:Session=Depends(db)):
    r=customer_request(rid,authorization.removeprefix('Bearer '),session,True)
    if r.order_id: return bespoke_view(r,session)
    if r.quote is None or r.quote!=data.total: raise HTTPException(409,'Quotation changed; refresh before accepting')
    o=Order(id=str(uuid.uuid4()),customer_name=r.customer_name,phone=r.phone,email=r.email,address=r.address,description=r.description,kind='bespoke',total=r.quote,verified_paid=Decimal('0'),status='awaiting_payment')
    session.add(o);session.flush();r.order_id=o.id;session.commit();return bespoke_view(r,session)

@app.get('/admin/bespoke-requests')
def admin_bespoke(who:str=Depends(admin_guard),session:Session=Depends(db)):
    return [{**bespoke_view(r,session),'customer_name':r.customer_name,'phone':r.phone,'email':r.email,'address':r.address,'description':r.description,'has_photo':r.mime is not None} for r in session.scalars(select(BespokeRequest)).all()]

@app.post('/admin/bespoke-requests/{rid}/quote')
def quote_bespoke(rid:str,data:BespokeQuote,who:str=Depends(admin_guard),session:Session=Depends(db)):
    r=session.scalar(select(BespokeRequest).where(BespokeRequest.id==rid).with_for_update())
    if not r: raise HTTPException(404,'Request not found')
    if r.order_id: raise HTTPException(409,'Accepted quotation cannot be changed')
    r.quote=data.total;session.commit();return bespoke_view(r,session)

@app.get('/admin/bespoke-requests/{rid}/photo')
def bespoke_photo(rid:str,who:str=Depends(admin_guard),session:Session=Depends(db)):
    r=session.get(BespokeRequest,rid)
    if not r or not r.photo: raise HTTPException(404,'Photo not found')
    return Response(r.photo,media_type=r.mime,headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Content-Disposition':'attachment; filename="inspiration"'})
