var gulp = require('gulp'),
    $ = {
        concat: require('gulp-concat'),
        fileInclude: require('gulp-include-inline'),
        htmlmin: require('gulp-htmlmin'),
        sass: require('gulp-sass'),
        sassvg: require('gulp-sassvg'),
        server: require('gulp-server-livereload'),
        svgSprite: require('gulp-svg-sprite'),
        template: require('gulp-md-template'),
        uglify: require('gulp-uglify')
    },
    fs = require("fs");


gulp.task('default', ['sass', 'combine', 'copy-assets']);

gulp.task('combine', ['svg','sass','javascript'], function () {
    var nzblnktpl = fs.readFileSync('./html/nzblnk.inc', 'utf8');
    return gulp.src('./html/*.html')
        .pipe($.template('./partials'))
        .pipe($.fileInclude({context: { nzblnk: nzblnktpl }}))
        .pipe($.htmlmin({collapseWhitespace: true, minifyCSS:true}))
        .pipe(gulp.dest('../'));
});

gulp.task('svg', function () {
    return gulp.src('./svg/logo-*.svg')
        .pipe($.svgSprite({
            mode: {
                inline: true,
                symbol: {
                    render: {
                        css: true,
                        scss: false
                    },
                    sprite: 'sprite.svg'
                }
            },
            svg: {
                xmlDeclaration: false,
                dimensionAttributes : true
            }
        }))
        .pipe(gulp.dest('./.inter'));
});
gulp.task('sassvg', function(){
    return gulp.src('./svg/icon-*.svg')
        .pipe($.sassvg({
            outputFolder: './.inter/',
            optimizeSvg: true
        }));
});

gulp.task('sass', function () {
    return gulp.src('./sass/**/*.scss')
        .pipe($.sass({style:'compressed'}).on('error', $.sass.logError))
        .pipe(gulp.dest('./.inter'));
});

gulp.task('javascript', function () {
    return gulp.src(['vendor/*.js', 'javascript/*.js'])
        .pipe($.concat('app.js'))
        .pipe($.uglify())
        .pipe(gulp.dest('./.inter'));
});

gulp.task('copy-assets', function () {
   return gulp.src('./assets/*')
       .pipe(gulp.dest('../'));

});

gulp.task('watch', function () {
    gulp.watch([
        './partials/*.md',
        './html/*.html',
        './sass/**/*.scss',
        './javascript/*.js'
    ], ['combine']);
});

gulp.task('webserver', ['watch'], function () {
    gulp.src('..')
        .pipe($.server({
            livereload: true,
            directoryListing: false,
            open: false
        }));
});