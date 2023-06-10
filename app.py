from flask import Flask, render_template, redirect, url_for, request
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, FloatField
from wtforms.validators import DataRequired, ValidationError, Optional
from sqlalchemy import desc
import requests
from pprint import pprint
import ast

# https://www.themoviedb.org/ 的API建置
API_KEY = "your api key"
headers = {
    "accept": "application/json",
    "Authorization": API_KEY
}

# 創建flask
app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
Bootstrap(app)

# 創建db
db = SQLAlchemy()
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///project_movie.db"
db.init_app(app)


class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), unique=True, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(500), nullable=False)
    rating = db.Column(db.Float, nullable=False)
    ranking = db.Column(db.Integer, nullable=False)
    review = db.Column(db.String(150), nullable=False)
    img_url = db.Column(db.String(300), nullable=False)


# Application Context 每个请求处理过程中创建的，并在请求处理完成后被销毁。它充当了访问应用程序全局对象和配置的中间层，并且在同一线程的多个请求之间共享。
with app.app_context():
    db.create_all()

# 嘗試添加資料一筆
# new_movie = Movie(
#     title="Phone Booth",
#     year=2002,
#     description="Publicist Stuart Shepard finds himself trapped in a phone booth, pinned down by an extortionist's sniper rifle. Unable to leave or receive outside help, Stuart's negotiation with the caller leads to a jaw-dropping climax.",
#     rating=7.3,
#     ranking=10,
#     review="My favourite character was the caller.",
#     img_url="https://image.tmdb.org/t/p/w500/tjrX2oWRCM3Tvarz38zlZM7Uc10.jpg"
# )
# with app.app_context():
#     db.session.add(new_movie)
#     db.session.commit()


def check_rating(form, field):
    if field.data is not None and (field.data > 10 or field.data < 0):
        raise ValidationError("Rating Must from 0 to 10 !")
    else:
        pass


class Edit_form(FlaskForm):
    # 解決驗證搞了很久 希望兩個都是option 但是好要填寫其中一個才能修改 , 希望在兩個都沒填寫的錯誤訊息出現在欄位旁邊 最後是用下面的 edit裡面實現,
    # 當驗證form 有雙空值的時候append錯誤訊息到欄位裡面
    rating = FloatField(label="Your Rating Out of 10 e.g. 7.5", validators=[Optional(), check_rating])
    review = StringField(label="Your Review")
    description = StringField(label="描述")
    submit = SubmitField(label="Done")


class Search_form(FlaskForm):
    search_name = StringField(label="Movie Title", validators=[DataRequired(message="需要輸入電影名稱")])
    submit = SubmitField(label="Search Movies")


@app.route("/")
def home():
    # desc 降冪排序 是sqlAlchemy來的
    card_datas = Movie.query.order_by(desc(Movie.rating)).all()
    # enumerate可以疊帶資料+生成一個順序數字
    for count, item in enumerate(card_datas, start=1):
        # 可以全部都修改 在一次commit
        item.ranking = count
    db.session.commit()
    return render_template("index.html", card_datas=card_datas)


@app.route("/edit/<title>", methods=['POST', 'GET'])
def edit_card(title):
    # 用title 因為是unique 撈資料
    card_data = Movie.query.filter_by(title=title).first()
    # obj是常見處理 將資料直接可視化出來 好處是 > 當你的form有創建這個欄位 form.populate_obj(card_data)
    # populate_obj你接收到對應的欄位都可以一次改寫
    form = Edit_form(obj=card_data)
    # 處理表單驗證
    if form.validate_on_submit():
        # 如果都沒填寫 更新錯誤資訊
        if not (form.rating.data or form.review.data):
            error_message = 'need type less one of them !'
            # 雙空值的時候append錯誤訊息
            form.rating.errors.append(error_message)
            form.review.errors.append(error_message)
            return render_template("edit.html", form=form, title=title)
        # 以下是至少填寫一個資料 這邊卡超久 第一次思考到 if not a or b => 這情況只有 a b都是False才會觸發
        # 相反 如果是and 就只有都False才不觸發 也就是 not 跟沒not是相反的
        elif form.rating.data and form.review.data:
            # 直接複寫資料populate_obj 把表單值複寫到對應屬性上 因為上面已經連結資料庫了
            form.populate_obj(card_data)
        elif form.rating.data:
            card_data.rating = float(form.rating.data)
        elif form.review.data:
            card_data.review = form.review.data
        db.session.commit()
        return redirect(url_for('home'))
    else:
        return render_template("edit.html", form=form, title=title)


@app.route('/delete/<title>')
def delete(title):
    db.session.delete(Movie.query.filter_by(title=title).first())
    db.session.commit()
    return redirect(url_for('home'))


@app.route('/search', methods=['POST', 'GET'])
def search_movie():
    form = Search_form()
    if form.validate_on_submit():
        movie_name = form.search_name.data
        movie_name = movie_name.replace(" ", "%20")
        url = f"https://api.themoviedb.org/3/search/movie?query={movie_name}&include_adult=false&language=en-US&page=1"
        response = requests.get(url, headers=headers).json()
        movie_list = response['results']
        return render_template("select.html", movie_list=movie_list)
    return render_template('add.html', form=form)

# 為了想省一次call API的次數所以用搜尋資料繼續做
@app.route('/add')
def add_movie():
    movie_data = request.args.get('movie_data')
    # 這邊發現在跟html交換資料後 取得的是字串, 但是有著字典形式 所以import ast去轉換, 用eval在ast的調用下不會執行字串內容, 如果單用eval會所以小心使用 , 轉換內容必須是單引號
    movie_data = ast.literal_eval(movie_data)
    # 為的就是能把資料寫進資料庫
    add_datas = Movie(
        title=movie_data['title'],
        # 把 2002-03-18這樣的資料切開只要年
        year=int(movie_data['release_date'].split('-')[0]),
        description=movie_data['overview'],
        rating=movie_data['vote_average'],
        ranking=10,
        review="Write somthing here",
        img_url=f"https://image.tmdb.org/t/p/w500{movie_data['poster_path']}"
    )
    # 添加內容
    db.session.add(add_datas)
    db.session.commit()
    return redirect(url_for('edit_card', title=movie_data['title']))


if __name__ == '__main__':
    app.run()
